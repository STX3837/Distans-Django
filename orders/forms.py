from django import forms

from .models import Pedido


class CheckoutBuyerForm(forms.Form):
    nombre = forms.CharField(label='Nombre', max_length=150)
    apellidos = forms.CharField(label='Apellidos', max_length=150)
    email = forms.EmailField(label='Correo')
    telefono = forms.CharField(label='Teléfono', max_length=20)

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user and user.is_authenticated:
            self.initial.setdefault('nombre', user.nombre)
            self.initial.setdefault('apellidos', user.apellidos)
            self.initial.setdefault('email', user.email)
            self.initial.setdefault('telefono', user.telefono)


class CheckoutAddressForm(forms.Form):
    direccion_envio = forms.CharField(label='Dirección de envío', max_length=255, widget=forms.TextInput(attrs={'placeholder': 'Calle, número, piso...'}))
    ciudad_envio = forms.CharField(label='Ciudad de envío', max_length=100)
    codigo_postal_envio = forms.CharField(label='Código postal de envío', max_length=20)
    direccion_facturacion = forms.CharField(label='Dirección de facturación', max_length=255, widget=forms.TextInput(attrs={'placeholder': 'Calle, número, piso...'}))
    ciudad_facturacion = forms.CharField(label='Ciudad de facturación', max_length=100)
    codigo_postal_facturacion = forms.CharField(label='Código postal de facturación', max_length=20)

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user and user.is_authenticated:
            self.initial.setdefault('direccion_envio', user.direccion)
            self.initial.setdefault('ciudad_envio', user.ciudad)
            self.initial.setdefault('codigo_postal_envio', user.codigo_postal)
            self.initial.setdefault('direccion_facturacion', user.direccion)
            self.initial.setdefault('ciudad_facturacion', user.ciudad)
            self.initial.setdefault('codigo_postal_facturacion', user.codigo_postal)


class CheckoutPaymentForm(forms.Form):
    metodo_pago = forms.ChoiceField(
        label='Método de pago',
        choices=Pedido.METODO_PAGO_CHOICES,
        widget=forms.RadioSelect,
    )