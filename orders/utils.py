from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timedelta, timezone as datetime_timezone

import stripe
from django.conf import settings
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils.crypto import get_random_string
from django.utils import timezone
from django.db.models import F

from carts.models import Carrito
from products.models import Producto

from .models import Pedido, ProductoPedido

TAX_RATE = Decimal('0.21')
SHIPPING_COST = Decimal('0.00')
ZERO = Decimal('0.00')


def _money(value):
    return Decimal(value).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def _unit_price_for_product(producto):
    if producto.tiene_oferta() and producto.precio_oferta is not None:
        return producto.precio_oferta
    return producto.precio


def _discount_for_product(producto):
    if producto.tiene_oferta() and producto.precio_oferta is not None:
        return producto.precio - producto.precio_oferta
    return ZERO


def build_cart_snapshot(request):
    if request.user.is_authenticated:
        carrito = Carrito.objects.filter(usuario=request.user).select_related('usuario').first()
        if not carrito:
            return {'cart': None, 'items': [], 'subtotal': ZERO, 'descuento': ZERO, 'impuesto': ZERO, 'coste_entrega': SHIPPING_COST, 'total': ZERO}

        items = []
        subtotal = ZERO
        descuento = ZERO
        for item in carrito.items.select_related('producto').all():
            unit_price = _unit_price_for_product(item.producto)
            original_price = item.producto.precio
            line_subtotal = _money(unit_price * item.cantidad)
            line_subtotal_bruto = _money(original_price * item.cantidad)
            line_discount = _money((original_price - unit_price) * item.cantidad)
            subtotal += line_subtotal_bruto
            descuento += line_discount
            items.append(
                {
                    'producto': item.producto,
                    'cantidad': item.cantidad,
                    'precio_original': _money(original_price),
                    'precio_unitario': _money(unit_price),
                    'descuento_unitario': _money(original_price - unit_price),
                    'subtotal_bruto': line_subtotal_bruto,
                    'subtotal_neto': line_subtotal,
                }
            )
    else:
        cart_data = request.session.get('cart', {})
        items = []
        subtotal = ZERO
        descuento = ZERO
        product_ids = [item.get('id') for item in cart_data.values() if item.get('id')]
        productos = Producto.objects.in_bulk(product_ids)

        for item in cart_data.values():
            producto = productos.get(item.get('id'))
            if not producto:
                continue

            cantidad = int(item.get('cantidad', 0))
            if cantidad <= 0:
                continue

            unit_price = _unit_price_for_product(producto)
            original_price = producto.precio
            line_subtotal = _money(unit_price * cantidad)
            line_subtotal_bruto = _money(original_price * cantidad)
            line_discount = _money((original_price - unit_price) * cantidad)
            subtotal += line_subtotal_bruto
            descuento += line_discount
            items.append(
                {
                    'producto': producto,
                    'cantidad': cantidad,
                    'precio_original': _money(original_price),
                    'precio_unitario': _money(unit_price),
                    'descuento_unitario': _money(original_price - unit_price),
                    'subtotal_bruto': line_subtotal_bruto,
                    'subtotal_neto': line_subtotal,
                }
            )

    base_imponible = subtotal - descuento
    physical_only_items = [
        line for line in items
        if not line['producto'].tienda or not line['producto'].tienda.permite_compra_online
    ]
    impuesto = _money(base_imponible * TAX_RATE)
    coste_entrega = SHIPPING_COST
    total = _money(base_imponible + impuesto + coste_entrega)

    return {
        'cart': None,
        'items': items,
		'physical_only_items': physical_only_items,
        'subtotal': _money(subtotal),
        'descuento': _money(descuento),
        'impuesto': impuesto,
        'coste_entrega': coste_entrega,
        'impuestos_y_envio': _money(impuesto + coste_entrega),
        'total': total,
    }


def _build_order_code():
    return f'PED-{get_random_string(10).upper()}'


def create_order_from_checkout(*, user, buyer_data, address_data, payment_method, cart_snapshot):
    if payment_method not in dict(Pedido.METODO_PAGO_CHOICES) or not cart_snapshot.get('items'):
        raise ValueError('El carrito o el método de pago no es válido.')
    physical_only_items = cart_snapshot.get('physical_only_items') or [
        line for line in cart_snapshot.get('items', [])
        if not line['producto'].tienda or not line['producto'].tienda.permite_compra_online
    ]
    if physical_only_items:
        raise ValidationError('Una tienda Freemium no puede recibir pedidos online.')
    base_imponible = cart_snapshot['subtotal'] - cart_snapshot['descuento']
    impuesto = cart_snapshot['impuesto']
    coste_entrega = cart_snapshot['coste_entrega']
    total = cart_snapshot['total']

    with transaction.atomic():
        # Lock rows to prevent concurrent purchases from overselling inventory.
        product_ids = [line['producto'].pk for line in cart_snapshot['items']]
        product_map = {
            p.pk: p
            for p in Producto.objects.select_for_update().filter(pk__in=product_ids).order_by('pk')
        }

        for line in cart_snapshot['items']:
            producto = product_map.get(line['producto'].pk)
            if not producto:
                raise ValueError('Uno de los productos ya no existe.')
            if producto.stock < line['cantidad']:
                raise ValueError(f"Stock insuficiente para {producto.nombre}.")
            if line['cantidad'] <= 0 or not producto.disponible or not producto.tienda.permite_compra_online:
                raise ValueError('Uno de los productos ya no está disponible para compra online.')
            if _unit_price_for_product(producto) != line['precio_unitario']:
                raise ValueError(f'El precio de {producto.nombre} ha cambiado. Revisa el carrito antes de confirmar.')

        pedido = Pedido.objects.create(
            codigo_pedido=_build_order_code(),
            usuario=user if user and user.is_authenticated else None,
            comprador_nombre=buyer_data['nombre'],
            comprador_apellidos=buyer_data['apellidos'],
            comprador_email=buyer_data['email'],
            telefono=buyer_data['telefono'],
            subtotal=cart_snapshot['subtotal'],
            descuento=cart_snapshot['descuento'],
            impuesto=impuesto,
            coste_entrega=coste_entrega,
            total=total,
            metodo_pago=payment_method,
            direccion_envio=address_data['direccion_envio'],
            ciudad_envio=address_data['ciudad_envio'],
            codigo_postal_envio=address_data['codigo_postal_envio'],
            direccion_facturacion=address_data['direccion_facturacion'],
            ciudad_facturacion=address_data['ciudad_facturacion'],
            codigo_postal_facturacion=address_data['codigo_postal_facturacion'],
            estado='preparacion' if payment_method == 'contrarrembolso' else 'pendiente_pago',
            estado_pago='cobro_tienda' if payment_method == 'contrarrembolso' else 'pendiente',
            stock_reservado=payment_method == 'pasarela',
            stock_descontado=True,
            reserva_expira=timezone.now() + timedelta(minutes=35) if payment_method == 'pasarela' else None,
        )

        for line in cart_snapshot['items']:
            producto = product_map[line['producto'].pk]
            producto.stock -= line['cantidad']
            producto.save(update_fields=['stock', 'updated_at'])

            ProductoPedido.objects.create(
                pedido=pedido,
                producto=producto,
                tienda=producto.tienda,
                nombre_producto=producto.nombre,
                nombre_tienda=producto.tienda.nombre if producto.tienda else '',
                cantidad=line['cantidad'],
                precio_unitario=line['precio_unitario'],
                total=line['subtotal_neto'],
            )

    return pedido


def release_order_stock_reservation(pedido):
    with transaction.atomic():
        pedido = Pedido.objects.select_for_update().prefetch_related('items__producto').get(pk=pedido.pk)
        if not pedido.stock_reservado or pedido.estado_pago == 'pagado':
            return False
        return _cancel_locked_order(pedido)


def _cancel_locked_order(pedido):
    if pedido.estado in {'cancelado', 'enviado', 'entregado'}:
        return False
    if pedido.stock_descontado or pedido.stock_reservado:
        for item in pedido.items.order_by('producto_id'):
            if item.producto_id:
                Producto.objects.filter(pk=item.producto_id).update(stock=F('stock') + item.cantidad)
    pedido.stock_descontado = False
    pedido.stock_reservado = False
    pedido.reserva_expira = None
    pedido.estado = 'cancelado'
    pedido.estado_pago = 'reembolso_pendiente' if pedido.estado_pago == 'pagado' else 'cancelado'
    pedido.save()
    return True


def cancel_pending_payment(pedido):
    """Close Stripe first so a live checkout cannot charge after releasing stock."""
    with transaction.atomic():
        locked = Pedido.objects.select_for_update().get(pk=pedido.pk)
        if locked.estado != 'pendiente_pago' or not locked.stock_reservado:
            return False
        if locked.stripe_checkout_session_id:
            session = get_stripe_session(locked.stripe_checkout_session_id)
            if session.payment_status == 'paid':
                mark_order_as_paid(locked)
                return False
            if session.status == 'open':
                stripe.checkout.Session.expire(session.id)
            elif session.status != 'expired':
                return False  # An asynchronous payment may still be processing.
        return _cancel_locked_order(locked)


def mark_order_as_paid(pedido):
    with transaction.atomic():
        locked = Pedido.objects.select_for_update().get(pk=pedido.pk)
        if locked.estado_pago in {'pagado', 'reembolso_pendiente'}:
            return
        if locked.estado == 'cancelado':
            locked.estado_pago = 'reembolso_pendiente'
        else:
            locked.estado_pago = 'pagado'
            if locked.estado == 'pendiente_pago':
                locked.estado = 'preparacion'
        locked.stock_reservado = False
        locked.reserva_expira = None
        locked.save()


def create_stripe_checkout_session(request, pedido):
    if not settings.STRIPE_SECRET_KEY:
        raise RuntimeError('Stripe no está configurado. Define STRIPE_SECRET_KEY en el entorno.')

    stripe.api_key = settings.STRIPE_SECRET_KEY

    session = stripe.checkout.Session.create(
        mode='payment',
        expires_at=int(pedido.reserva_expira.timestamp()),
        idempotency_key=f'pedido-{pedido.pk}-checkout',
        success_url=request.build_absolute_uri('/checkout/pago/exito/') + '?session_id={CHECKOUT_SESSION_ID}',
        cancel_url=request.build_absolute_uri(f'/checkout/pago/cancelado/?pedido_id={pedido.pk}'),
        customer_email=pedido.comprador_email,
        metadata={
            'pedido_id': str(pedido.pk),
            'codigo_pedido': pedido.codigo_pedido,
        },
        line_items=[
            {
                'price_data': {
                    'currency': 'eur',
                    'product_data': {
                        'name': f'Pedido {pedido.codigo_pedido}',
                        'description': f'Compra en DISTANS ({pedido.items.count()} productos).',
                    },
                    'unit_amount': int((pedido.total * 100).to_integral_value()),
                },
                'quantity': 1,
            }
        ],
    )

    pedido.stripe_checkout_session_id = session.id
    pedido.save(update_fields=['stripe_checkout_session_id', 'updated_at'])
    return session


def get_stripe_session(session_id):
    if not settings.STRIPE_SECRET_KEY:
        raise RuntimeError('Stripe no está configurado. Define STRIPE_SECRET_KEY en el entorno.')

    stripe.api_key = settings.STRIPE_SECRET_KEY
    return stripe.checkout.Session.retrieve(session_id)


@transaction.atomic
def create_premium_checkout_session(request, tienda):
    if not settings.STRIPE_SECRET_KEY:
        raise RuntimeError('Stripe no está configurado. Define STRIPE_SECRET_KEY en el entorno.')

    stripe.api_key = settings.STRIPE_SECRET_KEY
    tienda = type(tienda).objects.select_for_update().get(pk=tienda.pk)
    if tienda.stripe_premium_checkout_id:
        existing = stripe.checkout.Session.retrieve(tienda.stripe_premium_checkout_id)
        if existing.status == 'open':
            return existing
        if existing.status == 'complete':
            raise RuntimeError('Ya has contratado Premium. Espera a que Stripe confirme la suscripción.')
    session = stripe.checkout.Session.create(
        mode='subscription',
        idempotency_key=f'premium-{tienda.pk}-{tienda.stripe_subscription_id or "new"}-{tienda.stripe_premium_checkout_id or "initial"}',
        success_url=request.build_absolute_uri('/checkout/premium/exito/') + '?session_id={CHECKOUT_SESSION_ID}',
        cancel_url=request.build_absolute_uri('/checkout/premium/cancelado/'),
        customer_email=tienda.vendedor.email,
        metadata={
            'tipo': 'suscripcion_premium',
            'tienda_id': str(tienda.pk),
        },
        subscription_data={'metadata': {'tipo': 'suscripcion_premium', 'tienda_id': str(tienda.pk)}},
        line_items=[
            {
                'price_data': {
                    'currency': 'eur',
                    'product_data': {
                        'name': 'Suscripción Premium DISTANS',
                        'description': 'Acceso Premium durante 1 mes.',
                    },
                    'unit_amount': 1499,
                    'recurring': {'interval': 'month'},
                },
                'quantity': 1,
            }
        ],
    )
    tienda.stripe_premium_checkout_id = session.id
    tienda.save(update_fields=['stripe_premium_checkout_id', 'updated_at'])
    return session


def activate_premium_store(tienda, subscription_id, *, allow_replace=False):
    """Retrieve current Stripe state, rather than trusting event arrival order."""
    stripe.api_key = settings.STRIPE_SECRET_KEY
    with transaction.atomic():
        tienda = type(tienda).objects.select_for_update().get(pk=tienda.pk)
        subscription = stripe.Subscription.retrieve(subscription_id)
        metadata = subscription.get('metadata', {})
        if str(metadata.get('tienda_id')) != str(tienda.pk) or metadata.get('tipo') != 'suscripcion_premium':
            raise ValueError('La suscripción no pertenece a esta tienda.')
        if tienda.stripe_subscription_id and tienda.stripe_subscription_id != subscription_id and (not allow_replace or tienda.permite_compra_online):
            raise ValueError('La tienda ya tiene otra suscripción activa.')
        period_end = subscription.get('current_period_end')
        if not period_end:
            period_end = min((item.get('current_period_end', 0) for item in subscription.get('items', {}).get('data', [])), default=0)
        premium_hasta = datetime.fromtimestamp(period_end, datetime_timezone.utc) if period_end else None
        active = bool(subscription.get('status') == 'active' and premium_hasta and premium_hasta > timezone.now())
        tienda.stripe_subscription_id = subscription_id
        tienda.premium_hasta = premium_hasta
        tienda.fecha_renovacion = timezone.localdate(premium_hasta) if premium_hasta else None
        tienda.plan = tienda.Plan.PREMIUM if active else tienda.Plan.FREEMIUM
        tienda.suscripcion_activa = active
        tienda.pasarela_activa = active
        if subscription.get('status') in {'canceled', 'unpaid', 'incomplete_expired'}:
            tienda.stripe_premium_checkout_id = ''
        tienda.save()
