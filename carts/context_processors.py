from carts.models import Carrito


def cart_summary(request):
    """Datos mínimos del carrito para cabecera: cantidad total de unidades."""
    count = 0

    if request.user.is_authenticated and getattr(request.user, 'rol', None) == 'comprador':
        carrito = Carrito.objects.filter(usuario=request.user).first()
        if carrito is not None:
            count = sum(item.cantidad for item in carrito.items.all())
    elif request.session.get('guest'):
        cart_session = request.session.get('cart', {})
        for raw_item in cart_session.values():
            try:
                count += int(raw_item.get('cantidad', 0))
            except (TypeError, ValueError):
                continue

    return {'cart_item_count': count}
