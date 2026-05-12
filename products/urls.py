from django.urls import path

from . import views

urlpatterns = [
    path('vendedor/', views.seller_home, name='seller_home'),
    path('vendedor/tiendas/<int:pk>/', views.store_detail, name='store_detail'),
    path('vendedor/tiendas/<int:store_pk>/productos/nuevo/', views.product_create, name='product_create'),
    path('vendedor/tiendas/<int:store_pk>/productos/<int:pk>/editar/', views.product_update, name='product_update'),
    path('vendedor/tiendas/<int:store_pk>/productos/<int:pk>/eliminar/', views.product_delete, name='product_delete'),
]
