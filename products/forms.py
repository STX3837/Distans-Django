from django import forms

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
