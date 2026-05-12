from django.contrib import admin
from .models import Tienda


@admin.register(Tienda)
class TiendaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'vendedor', 'created_at', 'updated_at')
    search_fields = ('nombre', 'vendedor__username')
    readonly_fields = ('created_at', 'updated_at')

