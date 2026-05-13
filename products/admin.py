from django.contrib import admin
from .models import Producto


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'precio', 'precio_oferta', 'en_oferta', 'marca', 'categoria', 'tienda', 'disponible', 'destacado', 'stock')
    list_filter = ('disponible', 'destacado', 'en_oferta', 'categoria', 'tienda')
    search_fields = ('nombre', 'descripcion', 'marca')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('Información básica', {
            'fields': ('nombre', 'descripcion', 'marca', 'categoria', 'imagen', 'tienda')
        }),
        ('Precios', {
            'fields': ('precio', 'en_oferta', 'precio_oferta')
        }),
        ('Estado', {
            'fields': ('disponible', 'destacado', 'stock')
        }),
        ('Fechas', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    def save_model(self, request, obj, form, change):
        """Ejecuta validación antes de guardar"""
        obj.full_clean()  # Ejecuta clean() del modelo
        super().save_model(request, obj, form, change)
