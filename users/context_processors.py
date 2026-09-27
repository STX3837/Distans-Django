from .models import Favorite, User


def favorite_ids(request):
    if not request.user.is_authenticated or request.user.rol != User.Role.BUYER:
        return {'favorite_product_ids': set(), 'favorite_store_ids': set()}

    favorites = Favorite.objects.filter(usuario=request.user)
    return {
        'favorite_product_ids': set(favorites.filter(producto__isnull=False).values_list('producto_id', flat=True)),
        'favorite_store_ids': set(favorites.filter(tienda__isnull=False).values_list('tienda_id', flat=True)),
    }