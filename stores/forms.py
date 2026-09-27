from django import forms
from django.db.models import Q
from users.models import User

from .models import Tienda


class SellerChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, user):
        return user.email


class TiendaForm(forms.ModelForm):
    vendedor = SellerChoiceField(
        label='Vendedor',
        queryset=User.objects.none(),
        empty_label='Selecciona un vendedor',
    )
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
            'nombre', 'vendedor', 'descripcion', 'direccion', 'horario', 'informacion_apertura',
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        available_sellers = User.objects.filter(
            rol=User.Role.SELLER,
            tienda__isnull=True,
        )
        if self.instance.pk and self.instance.vendedor_id:
            available_sellers = User.objects.filter(
                rol=User.Role.SELLER,
            ).filter(
                Q(tienda__isnull=True) | Q(pk=self.instance.vendedor_id)
            )
        self.fields['vendedor'].queryset = available_sellers.order_by('email')


class SellerTiendaForm(forms.ModelForm):
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
            'nombre', 'descripcion', 'direccion', 'horario',
            'informacion_apertura', 'latitud', 'longitud', 'imagen',
        ]
        widgets = {
            'nombre': forms.TextInput(attrs={'placeholder': 'Nombre de la tienda'}),
            'descripcion': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Descripción'}),
            'direccion': forms.TextInput(attrs={'placeholder': 'Dirección'}),
            'horario': forms.TextInput(attrs={'placeholder': 'Lunes a viernes, 09:00-20:00'}),
            'informacion_apertura': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'Información adicional de apertura y atención',
            }),
        }
