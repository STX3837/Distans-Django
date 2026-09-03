from django.urls import path

from . import views

urlpatterns = [
    path('checkout/comprador/', views.checkout_customer, name='checkout_customer'),
    path('checkout/direcciones/', views.checkout_address, name='checkout_address'),
    path('checkout/pago/', views.checkout_payment, name='checkout_payment'),
    path('checkout/completado/', views.checkout_complete, name='checkout_complete'),
    path('pedidos/mis-pedidos/', views.order_history, name='order_history'),
    path('pedidos/buscar/', views.order_lookup, name='order_lookup'),
    path('pedidos/<str:codigo_pedido>/', views.order_detail, name='order_detail'),
    path('gestion/pedidos/', views.vendor_order_list, name='vendor_order_list'),
    path('gestion/pedidos/<str:codigo_pedido>/', views.vendor_order_detail, name='vendor_order_detail'),
]