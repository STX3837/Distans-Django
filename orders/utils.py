from decimal import Decimal, ROUND_HALF_UP

import stripe
from django.conf import settings
from django.db import transaction
from django.utils.crypto import get_random_string

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
    impuesto = _money(base_imponible * TAX_RATE)
    coste_entrega = SHIPPING_COST
    total = _money(base_imponible + impuesto + coste_entrega)

    return {
        'cart': None,
        'items': items,
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
    base_imponible = cart_snapshot['subtotal'] - cart_snapshot['descuento']
    impuesto = cart_snapshot['impuesto']
    coste_entrega = cart_snapshot['coste_entrega']
    total = cart_snapshot['total']

    with transaction.atomic():
        # Lock rows to prevent concurrent purchases from overselling inventory.
        product_ids = [line['producto'].pk for line in cart_snapshot['items']]
        product_map = {
            p.pk: p
            for p in Producto.objects.select_for_update().filter(pk__in=product_ids)
        }

        for line in cart_snapshot['items']:
            producto = product_map.get(line['producto'].pk)
            if not producto:
                raise ValueError('Uno de los productos ya no existe.')
            if producto.stock < line['cantidad']:
                raise ValueError(f"Stock insuficiente para {producto.nombre}.")

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
            estado='pendiente_pago',
            stock_reservado=True,
        )

        for line in cart_snapshot['items']:
            producto = product_map[line['producto'].pk]
            producto.stock -= line['cantidad']
            producto.save(update_fields=['stock', 'updated_at'])

            ProductoPedido.objects.create(
                pedido=pedido,
                producto=producto,
                cantidad=line['cantidad'],
                precio_unitario=line['precio_unitario'],
                total=line['subtotal_neto'],
            )

    return pedido


def process_secure_payment(pedido, payment_method):
    reference = f'PAY-{pedido.codigo_pedido}-{payment_method[:3].upper()}'
    return {
        'success': True,
        'reference': reference,
        'message': 'La transacción se ha validado correctamente en un entorno seguro.',
    }


def release_order_stock_reservation(pedido):
    if not pedido.stock_reservado:
        return

    with transaction.atomic():
        pedido = Pedido.objects.select_for_update().prefetch_related('items__producto').get(pk=pedido.pk)
        if not pedido.stock_reservado:
            return

        for item in pedido.items.all():
            producto = item.producto
            producto.stock += item.cantidad
            producto.save(update_fields=['stock', 'updated_at'])

        pedido.stock_reservado = False
        pedido.estado = 'cancelado'
        pedido.save(update_fields=['stock_reservado', 'estado', 'updated_at'])


def mark_order_as_paid(pedido):
    pedido.estado = 'completado'
    pedido.stock_reservado = False
    pedido.save(update_fields=['estado', 'stock_reservado', 'updated_at'])


def create_stripe_checkout_session(request, pedido):
    if not settings.STRIPE_SECRET_KEY:
        raise RuntimeError('Stripe no está configurado. Define STRIPE_SECRET_KEY en el entorno.')

    stripe.api_key = settings.STRIPE_SECRET_KEY

    session = stripe.checkout.Session.create(
        mode='payment',
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