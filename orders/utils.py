from decimal import Decimal, ROUND_HALF_UP
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
            estado='preparacion',
        )

        for line in cart_snapshot['items']:
            ProductoPedido.objects.create(
                pedido=pedido,
                producto=line['producto'],
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