from django import forms
from django.contrib.auth import get_user_model

UserModel = get_user_model()


class SignUpForm(forms.ModelForm):
    password1 = forms.CharField(label='Contraseña', widget=forms.PasswordInput)
    password2 = forms.CharField(label='Repetir contraseña', widget=forms.PasswordInput)
    rol = forms.ChoiceField(
        label='Rol',
        choices=[
            (UserModel.Role.BUYER, UserModel.Role.BUYER.label),
            (UserModel.Role.SELLER, UserModel.Role.SELLER.label),
        ],
        initial=UserModel.Role.BUYER,
        widget=forms.RadioSelect,
    )

    class Meta:
        model = UserModel
        fields = ['nombre', 'apellidos', 'email', 'telefono', 'direccion', 'ciudad', 'codigo_postal', 'rol']

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')

        if password1 and password2:
            if password1 != password2:
                raise forms.ValidationError('Las contraseñas no coinciden.')
        elif not password1 or not password2:
            raise forms.ValidationError('Debes indicar una contraseña.')

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password1'])
        if commit:
            user.save()
        return user


class AccountUpdateForm(forms.ModelForm):
    class Meta:
        model = UserModel
        fields = ['nombre', 'apellidos', 'email', 'telefono', 'direccion', 'ciudad', 'codigo_postal']


class AdminUserForm(forms.ModelForm):
    password1 = forms.CharField(label='Contraseña', required=False, widget=forms.PasswordInput)
    password2 = forms.CharField(label='Repetir contraseña', required=False, widget=forms.PasswordInput)

    class Meta:
        model = UserModel
        fields = [
            'nombre',
            'apellidos',
            'email',
            'telefono',
            'direccion',
            'ciudad',
            'codigo_postal',
            'rol',
            'is_active',
        ]

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')

        if self.instance.pk:
            if password1 or password2:
                if password1 != password2:
                    raise forms.ValidationError('Las contraseñas no coinciden.')
        else:
            if not password1 or not password2:
                raise forms.ValidationError('Debes indicar una contraseña para crear el usuario.')
            if password1 != password2:
                raise forms.ValidationError('Las contraseñas no coinciden.')

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data.get('password1')

        if password:
            user.set_password(password)

        if commit:
            user.save()
            self.save_m2m()

        return user