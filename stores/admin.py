from django.contrib import admin
from .models import Tienda


@admin.register(Tienda)
class TiendaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'vendedor', 'plan', 'suscripcion_activa', 'pasarela_activa', 'fecha_renovacion', 'created_at', 'updated_at')
    list_filter = ('plan', 'suscripcion_activa', 'pasarela_activa')
    search_fields = ('nombre', 'vendedor__username')
    readonly_fields = ('fecha_alta', 'created_at', 'updated_at', 'stripe_subscription_id', 'stripe_premium_checkout_id', 'premium_hasta')
