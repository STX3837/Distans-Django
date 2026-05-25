from django import forms
from .models import Tienda


class TiendaForm(forms.ModelForm):
    latitud = forms.DecimalField(
        max_digits=9,
        decimal_places=6,
        required=True,
        widget=forms.HiddenInput(),
    )
    longitud = forms.DecimalField(
        max_digits=9,
        decimal_places=6,
        required=True,
        widget=forms.HiddenInput(),
    )

    class Meta:
        model = Tienda
        fields = ['nombre', 'descripcion', 'direccion', 'latitud', 'longitud', 'imagen']
        widgets = {
            'nombre': forms.TextInput(attrs={'placeholder': 'Nombre de la tienda'}),
            'descripcion': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Descripción'}),
            'direccion': forms.TextInput(attrs={'placeholder': 'Dirección'}),
        }
