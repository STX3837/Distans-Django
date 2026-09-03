from django.urls import path

from . import views

urlpatterns = [
    path('checkout/comprador/', views.checkout_customer, name='checkout_customer'),
    path('checkout/direcciones/', views.checkout_address, name='checkout_address'),
    path('checkout/pago/', views.checkout_payment, name='checkout_payment'),
    path('checkout/pago/exito/', views.checkout_payment_success, name='checkout_payment_success'),
    path('checkout/pago/cancelado/', views.checkout_payment_cancel, name='checkout_payment_cancel'),
    path('api/pagos/stripe/webhook/', views.stripe_webhook, name='stripe_webhook'),
    path('checkout/completado/', views.checkout_complete, name='checkout_complete'),
]