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
        fields = [
            'nombre', 'descripcion', 'direccion', 'horario', 'informacion_apertura',
            'plan', 'suscripcion_activa', 'pasarela_activa', 'fecha_renovacion', 'latitud', 'longitud', 'imagen',
        ]
        widgets = {
            'nombre': forms.TextInput(attrs={'placeholder': 'Nombre de la tienda'}),
            'descripcion': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Descripción'}),
            'direccion': forms.TextInput(attrs={'placeholder': 'Dirección'}),
            'horario': forms.TextInput(attrs={'placeholder': 'Lunes a viernes, 09:00-20:00'}),
            'informacion_apertura': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Información adicional de apertura y atención'}),
            'fecha_renovacion': forms.DateInput(attrs={'type': 'date'}),
        }
