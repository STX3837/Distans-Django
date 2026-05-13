from django import forms
from .models import Tienda


class TiendaForm(forms.ModelForm):
    class Meta:
        model = Tienda
        fields = ['nombre', 'descripcion', 'direccion', 'imagen']
        widgets = {
            'nombre': forms.TextInput(attrs={'placeholder': 'Nombre de la tienda'}),
            'descripcion': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Descripción'}),
            'direccion': forms.TextInput(attrs={'placeholder': 'Dirección'}),
        }
