from django import forms
from django.core.exceptions import ValidationError

from .models import Producto


class ProductoForm(forms.ModelForm):
    class Meta:
        model = Producto
        fields = [
            'nombre',
            'descripcion',
            'precio',
            'en_oferta',
            'precio_oferta',
            'marca',
            'categoria',
            'imagen',
            'destacado',
            'disponible',
            'stock',
        ]
        widgets = {
            'descripcion': forms.Textarea(attrs={'rows': 4}),
        }
    
    def clean(self):
        """Validación adicional del formulario"""
        cleaned_data = super().clean()
        precio = cleaned_data.get('precio')
        precio_oferta = cleaned_data.get('precio_oferta')
        
        # Validar que precio_oferta, si existe, sea mayor que 0
        if precio_oferta is not None and precio_oferta <= 0:
            self.add_error('precio_oferta', 'El precio en oferta debe ser mayor que 0.')
        
        # Validar que precio_oferta no sea mayor que el precio normal
        if precio_oferta is not None and precio and precio_oferta > precio:
            self.add_error('precio_oferta', 'El precio en oferta no puede ser mayor que el precio normal.')
        
        return cleaned_data
