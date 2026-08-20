from django.urls import path

from . import views

urlpatterns = [
    path('checkout/comprador/', views.checkout_customer, name='checkout_customer'),
    path('checkout/direcciones/', views.checkout_address, name='checkout_address'),
    path('checkout/pago/', views.checkout_payment, name='checkout_payment'),
    path('checkout/completado/', views.checkout_complete, name='checkout_complete'),
]