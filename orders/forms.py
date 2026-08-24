from django import forms
from django.core.validators import RegexValidator

from .models import Pedido


NAME_VALIDATOR = RegexValidator(
    regex=r"^[A-Za-zÁÉÍÓÚÜÑáéíóúüñ' -]+$",
    message='Usa solo letras y espacios.',
)

CITY_VALIDATOR = RegexValidator(
    regex=r"^[A-Za-zÁÉÍÓÚÜÑáéíóúüñ' -]+$",
    message='La ciudad solo puede contener letras y espacios.',
)

PHONE_VALIDATOR = RegexValidator(
    regex=r'^(\+\d{1,3}[ -]?)?[\d -]{9,20}$',
    message='Introduce un teléfono válido (9 a 15 dígitos, con prefijo opcional).',
)

POSTAL_CODE_VALIDATOR = RegexValidator(
    regex=r'^(0[1-9]|[1-4][0-9]|5[0-2])\d{3}$',
    message='Introduce un código postal español válido de 5 dígitos.',
)


def _clean_spaces(value):
    return ' '.join((value or '').strip().split())


def _validate_address(value):
    cleaned = _clean_spaces(value)
    if len(cleaned) < 5:
        raise forms.ValidationError('La dirección es demasiado corta.')
    if not any(ch.isalpha() for ch in cleaned):
        raise forms.ValidationError('La dirección debe incluir texto válido.')
    if not any(ch.isdigit() for ch in cleaned):
        raise forms.ValidationError('La dirección debe incluir un número (por ejemplo, calle y número).')
    return cleaned


class CheckoutBuyerForm(forms.Form):
    nombre = forms.CharField(
        label='Nombre',
        max_length=150,
        validators=[NAME_VALIDATOR],
        error_messages={
            'required': 'El nombre es obligatorio.',
            'max_length': 'El nombre no puede superar los 150 caracteres.',
        },
    )
    apellidos = forms.CharField(
        label='Apellidos',
        max_length=150,
        validators=[NAME_VALIDATOR],
        error_messages={
            'required': 'Los apellidos son obligatorios.',
            'max_length': 'Los apellidos no pueden superar los 150 caracteres.',
        },
    )
    email = forms.EmailField(
        label='Correo',
        error_messages={
            'required': 'El correo electrónico es obligatorio.',
            'invalid': 'Introduce un correo electrónico válido.',
        },
    )
    telefono = forms.CharField(
        label='Teléfono',
        max_length=20,
        validators=[PHONE_VALIDATOR],
        error_messages={
            'required': 'El teléfono es obligatorio.',
            'max_length': 'El teléfono no puede superar los 20 caracteres.',
        },
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user and user.is_authenticated:
            self.initial.setdefault('nombre', user.nombre)
            self.initial.setdefault('apellidos', user.apellidos)
            self.initial.setdefault('email', user.email)
            self.initial.setdefault('telefono', user.telefono)

    def clean_nombre(self):
        return _clean_spaces(self.cleaned_data['nombre'])

    def clean_apellidos(self):
        return _clean_spaces(self.cleaned_data['apellidos'])

    def clean_telefono(self):
        normalized = self.cleaned_data['telefono'].replace(' ', '').replace('-', '')
        prefix = normalized[1:] if normalized.startswith('+') else normalized
        if not prefix.isdigit() or not (9 <= len(prefix) <= 15):
            raise forms.ValidationError('Introduce un teléfono válido (9 a 15 dígitos, con prefijo opcional).')
        return normalized


class CheckoutAddressForm(forms.Form):
    direccion_envio = forms.CharField(
        label='Dirección de envío',
        max_length=255,
        widget=forms.TextInput(attrs={'placeholder': 'Calle, número, piso...'}),
        error_messages={
            'required': 'La dirección de envío es obligatoria.',
            'max_length': 'La dirección de envío no puede superar los 255 caracteres.',
        },
    )
    ciudad_envio = forms.CharField(
        label='Ciudad de envío',
        max_length=100,
        validators=[CITY_VALIDATOR],
        error_messages={
            'required': 'La ciudad de envío es obligatoria.',
            'max_length': 'La ciudad de envío no puede superar los 100 caracteres.',
        },
    )
    codigo_postal_envio = forms.CharField(
        label='Código postal de envío',
        max_length=20,
        validators=[POSTAL_CODE_VALIDATOR],
        error_messages={
            'required': 'El código postal de envío es obligatorio.',
            'max_length': 'El código postal de envío no puede superar los 20 caracteres.',
        },
    )
    direccion_facturacion = forms.CharField(
        label='Dirección de facturación',
        max_length=255,
        widget=forms.TextInput(attrs={'placeholder': 'Calle, número, piso...'}),
        error_messages={
            'required': 'La dirección de facturación es obligatoria.',
            'max_length': 'La dirección de facturación no puede superar los 255 caracteres.',
        },
    )
    ciudad_facturacion = forms.CharField(
        label='Ciudad de facturación',
        max_length=100,
        validators=[CITY_VALIDATOR],
        error_messages={
            'required': 'La ciudad de facturación es obligatoria.',
            'max_length': 'La ciudad de facturación no puede superar los 100 caracteres.',
        },
    )
    codigo_postal_facturacion = forms.CharField(
        label='Código postal de facturación',
        max_length=20,
        validators=[POSTAL_CODE_VALIDATOR],
        error_messages={
            'required': 'El código postal de facturación es obligatorio.',
            'max_length': 'El código postal de facturación no puede superar los 20 caracteres.',
        },
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user and user.is_authenticated:
            self.initial.setdefault('direccion_envio', user.direccion)
            self.initial.setdefault('ciudad_envio', user.ciudad)
            self.initial.setdefault('codigo_postal_envio', user.codigo_postal)
            self.initial.setdefault('direccion_facturacion', user.direccion)
            self.initial.setdefault('ciudad_facturacion', user.ciudad)
            self.initial.setdefault('codigo_postal_facturacion', user.codigo_postal)

    def clean_direccion_envio(self):
        return _validate_address(self.cleaned_data['direccion_envio'])

    def clean_ciudad_envio(self):
        return _clean_spaces(self.cleaned_data['ciudad_envio'])

    def clean_codigo_postal_envio(self):
        return self.cleaned_data['codigo_postal_envio'].strip()

    def clean_direccion_facturacion(self):
        return _validate_address(self.cleaned_data['direccion_facturacion'])

    def clean_ciudad_facturacion(self):
        return _clean_spaces(self.cleaned_data['ciudad_facturacion'])

    def clean_codigo_postal_facturacion(self):
        return self.cleaned_data['codigo_postal_facturacion'].strip()


class CheckoutPaymentForm(forms.Form):
    metodo_pago = forms.ChoiceField(
        label='Método de pago',
        choices=Pedido.METODO_PAGO_CHOICES,
        widget=forms.RadioSelect,
    )