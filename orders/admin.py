from django.contrib import admin
from .models import Pedido, ProductoPedido


class ProductoPedidoInline(admin.TabularInline):
    model = ProductoPedido
    extra = 1
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = ('codigo_pedido', 'usuario', 'estado', 'total', 'fecha', 'created_at')
    list_filter = ('estado', 'metodo_pago', 'fecha')
    search_fields = ('codigo_pedido', 'usuario__username', 'usuario__email')
    readonly_fields = ('created_at', 'updated_at')
    inlines = [ProductoPedidoInline]
    fieldsets = (
        ('Información del pedido', {
            'fields': ('codigo_pedido', 'usuario', 'fecha', 'estado')
        }),
        ('Precios', {
            'fields': ('subtotal', 'impuesto', 'coste_entrega', 'total')
        }),
        ('Pago y envío', {
            'fields': ('metodo_pago', 'direccion_envio', 'direccion_facturacion', 'telefono')
        }),
        ('Fechas', {
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(ProductoPedido)
class ProductoPedidoAdmin(admin.ModelAdmin):
    list_display = ('pedido', 'producto', 'cantidad', 'precio_unitario', 'total')
    list_filter = ('pedido__estado', 'producto')
    search_fields = ('pedido__codigo_pedido', 'producto__nombre')
    readonly_fields = ('created_at', 'updated_at')
