from django.urls import path

from . import views
from stores import views as store_views

urlpatterns = [
    # Vendedor
    path('vendedor/', views.seller_home, name='seller_home'),
    path('vendedor/tiendas/<int:pk>/', views.store_detail, name='store_detail'),
    path('vendedor/tiendas/<int:pk>/editar/', views.store_update, name='store_update'),
    path('vendedor/tiendas/<int:store_pk>/productos/nuevo/', views.product_create, name='product_create'),
    path('vendedor/tiendas/<int:store_pk>/productos/<int:pk>/editar/', views.product_update, name='product_update'),
    path('vendedor/tiendas/<int:store_pk>/productos/<int:pk>/eliminar/', views.product_delete, name='product_delete'),
    
    # Comprador - Público
    path('busqueda/ubicacion/', store_views.set_search_location, name='set_search_location'),
    path('busqueda/radio/', store_views.set_search_radius, name='set_search_radius'),
    path('productos/', views.catalog, name='catalog'),
    path('tiendas/<int:pk>/productos/', views.store_products, name='store_products'),
    path('productos/<int:pk>/', views.product_detail, name='product_detail'),
    path('productos/<int:product_pk>/agregar-carrito/', views.add_to_cart, name='add_to_cart'),
    path('carrito/', views.cart_view, name='cart_view'),
]
