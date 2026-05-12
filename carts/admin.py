from django.contrib import admin
from .models import Carrito, ProductoCarrito


class ProductoCarritoInline(admin.TabularInline):
    model = ProductoCarrito
    extra = 1
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Carrito)
class CarritoAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'created_at', 'updated_at')
    search_fields = ('usuario__username',)
    readonly_fields = ('created_at', 'updated_at')
    inlines = [ProductoCarritoInline]


@admin.register(ProductoCarrito)
class ProductoCarritoAdmin(admin.ModelAdmin):
    list_display = ('carrito', 'producto', 'cantidad', 'updated_at')
    list_filter = ('carrito__usuario', 'producto')
    search_fields = ('carrito__usuario__username', 'producto__nombre')
    readonly_fields = ('created_at', 'updated_at')
