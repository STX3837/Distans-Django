from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .forms import AccountUpdateForm, AdminUserForm, SignUpForm


User = get_user_model()


class UserModelTests(TestCase):
    def test_create_user_hashes_password_and_defaults_to_buyer(self):
        user = User.objects.create_user(
            email='comprador@example.com',
            password='secret123',
            nombre='Ana',
            apellidos='Perez',
        )

        self.assertEqual(user.rol, User.Role.BUYER)
        self.assertTrue(user.check_password('secret123'))
        self.assertTrue(user.password.startswith('pbkdf2_'))

    def test_create_superuser_uses_admin_role(self):
        superuser = User.objects.create_superuser(
            email='admin@example.com',
            password='secret123',
            nombre='Admin',
            apellidos='User',
        )

        self.assertEqual(superuser.rol, User.Role.ADMIN)
        self.assertTrue(superuser.is_staff)
        self.assertTrue(superuser.is_superuser)


class AccountViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='usuario@example.com',
            password='secret123',
            nombre='Luis',
            apellidos='Lopez',
        )

    def test_account_view_requires_authentication(self):
        response = self.client.get(reverse('account_detail'))

        self.assertEqual(response.status_code, 302)

    def test_account_view_updates_user_data(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('account_detail'),
            data={
                'nombre': 'Luis',
                'apellidos': 'Lopez',
                'email': 'usuario@example.com',
                'telefono': '600123123',
                'direccion': 'Calle Mayor 1',
                'ciudad': 'Madrid',
                'codigo_postal': '28001',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertEqual(self.user.telefono, '600123123')
        self.assertEqual(self.user.ciudad, 'Madrid')

    def test_account_template_renders_expected_controls(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse('account_detail'))

        self.assertContains(response, '<h1>Mi Cuenta</h1>', html=True)
        self.assertContains(response, 'Guardar Cambios')


class RootUrlTests(TestCase):
    def test_root_redirects_to_login(self):
        response = self.client.get('/')

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, '/accounts/login/', fetch_redirect_response=False)


class AdminUserViewTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            email='admin@example.com',
            password='secret123',
            nombre='Admin',
            apellidos='User',
        )
        self.other_user = User.objects.create_user(
            email='comprador@example.com',
            password='secret123',
            nombre='Ana',
            apellidos='Perez',
        )

    def test_admin_views_require_staff_access(self):
        self.client.force_login(self.other_user)

        response = self.client.get(reverse('admin_user_list'))

        self.assertEqual(response.status_code, 302)

    def test_admin_can_list_users(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse('admin_user_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<h1>Gestión de Usuarios</h1>', html=True)
        self.assertContains(response, 'Crear Usuario')
        self.assertContains(response, 'comprador@example.com')

    def test_admin_can_create_user_with_seller_role(self):
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse('admin_user_create'),
            data={
                'nombre': 'Carlos',
                'apellidos': 'Ruiz',
                'email': 'vendedor@example.com',
                'telefono': '611111111',
                'direccion': 'Avenida 2',
                'ciudad': 'Sevilla',
                'codigo_postal': '41001',
                'rol': User.Role.SELLER,
                'is_active': 'on',
                'password1': 'secret123',
                'password2': 'secret123',
            },
        )

        self.assertEqual(response.status_code, 302)
        created_user = User.objects.get(email='vendedor@example.com')
        self.assertEqual(created_user.rol, User.Role.SELLER)
        self.assertTrue(created_user.check_password('secret123'))

    def test_admin_create_template_renders_form_title(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse('admin_user_create'))

        self.assertContains(response, '<h1>Crear usuario</h1>', html=True)
        self.assertContains(response, 'Guardar')

    def test_admin_can_update_user_role(self):
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse('admin_user_update', args=[self.other_user.pk]),
            data={
                'nombre': 'Ana',
                'apellidos': 'Perez',
                'email': 'comprador@example.com',
                'telefono': '622222222',
                'direccion': 'Calle Nueva 3',
                'ciudad': 'Valencia',
                'codigo_postal': '46001',
                'rol': User.Role.SELLER,
                'is_active': 'on',
                'password1': '',
                'password2': '',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.other_user.refresh_from_db()
        self.assertEqual(self.other_user.rol, User.Role.SELLER)
        self.assertEqual(self.other_user.telefono, '622222222')

    def test_admin_update_template_renders_form_title(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse('admin_user_update', args=[self.other_user.pk]))

        self.assertContains(response, '<h1>Editar usuario</h1>', html=True)
        self.assertContains(response, 'Guardar')

    def test_admin_can_delete_user(self):
        self.client.force_login(self.admin)

        response = self.client.post(reverse('admin_user_delete', args=[self.other_user.pk]))

        self.assertEqual(response.status_code, 302)
        self.assertFalse(User.objects.filter(pk=self.other_user.pk).exists())

    def test_admin_delete_template_renders_confirmation(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse('admin_user_delete', args=[self.other_user.pk]))

        self.assertContains(response, 'Eliminar Usuario')
        self.assertContains(response, self.other_user.email)


class UserFormTests(TestCase):
    def test_admin_user_form_requires_matching_passwords_on_create(self):
        form = AdminUserForm(
            data={
                'nombre': 'Carlos',
                'apellidos': 'Ruiz',
                'email': 'carlos@example.com',
                'telefono': '611111111',
                'direccion': 'Avenida 2',
                'ciudad': 'Sevilla',
                'codigo_postal': '41001',
                'rol': User.Role.SELLER,
                'is_active': True,
                'password1': 'secret123',
                'password2': 'different123',
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn('Las contrasenas no coinciden.', form.non_field_errors())

    def test_admin_user_form_requires_password_on_create(self):
        form = AdminUserForm(
            data={
                'nombre': 'Carlos',
                'apellidos': 'Ruiz',
                'email': 'carlos@example.com',
                'telefono': '611111111',
                'direccion': 'Avenida 2',
                'ciudad': 'Sevilla',
                'codigo_postal': '41001',
                'rol': User.Role.SELLER,
                'is_active': True,
                'password1': '',
                'password2': '',
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn('Debes indicar una contrasena para crear el usuario.', form.non_field_errors())

    def test_admin_user_form_hashes_password_when_valid(self):
        form = AdminUserForm(
            data={
                'nombre': 'Carlos',
                'apellidos': 'Ruiz',
                'email': 'carlos@example.com',
                'telefono': '611111111',
                'direccion': 'Avenida 2',
                'ciudad': 'Sevilla',
                'codigo_postal': '41001',
                'rol': User.Role.SELLER,
                'is_active': True,
                'password1': 'secret123',
                'password2': 'secret123',
            }
        )

        self.assertTrue(form.is_valid())
        user = form.save()
        self.assertTrue(user.check_password('secret123'))
        self.assertEqual(user.rol, User.Role.SELLER)

    def test_account_update_form_accepts_account_fields(self):
        user = User.objects.create_user(
            email='form@example.com',
            password='secret123',
            nombre='Eva',
            apellidos='Santos',
        )

        form = AccountUpdateForm(
            data={
                'nombre': 'Eva',
                'apellidos': 'Santos',
                'email': 'form@example.com',
                'telefono': '633333333',
                'direccion': 'Calle Falsa 123',
                'ciudad': 'Bilbao',
                'codigo_postal': '48001',
            },
            instance=user,
        )

        self.assertTrue(form.is_valid())
        updated_user = form.save()
        self.assertEqual(updated_user.ciudad, 'Bilbao')


class SignUpViewTests(TestCase):
    def test_signup_view_is_accessible(self):
        response = self.client.get(reverse('signup'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<h1>Crear Cuenta</h1>', html=True)

    def test_signup_creates_user_with_buyer_role(self):
        response = self.client.post(
            reverse('signup'),
            data={
                'nombre': 'Juan',
                'apellidos': 'Garcia',
                'email': 'juan@example.com',
                'telefono': '612345678',
                'direccion': 'Calle Test 1',
                'ciudad': 'Madrid',
                'codigo_postal': '28001',
                'rol': User.Role.BUYER,
                'password1': 'secret123',
                'password2': 'secret123',
            },
        )

        self.assertEqual(response.status_code, 302)
        user = User.objects.get(email='juan@example.com')
        self.assertEqual(user.nombre, 'Juan')
        self.assertEqual(user.rol, User.Role.BUYER)
        self.assertEqual(user.ciudad, 'Madrid')
        self.assertTrue(user.check_password('secret123'))

    def test_signup_form_rejects_mismatched_passwords(self):
        response = self.client.post(
            reverse('signup'),
            data={
                'nombre': 'Juan',
                'apellidos': 'Garcia',
                'email': 'juan@example.com',
                'telefono': '612345678',
                'direccion': 'Calle Test 1',
                'ciudad': 'Madrid',
                'codigo_postal': '28001',
                'rol': User.Role.BUYER,
                'password1': 'secret123',
                'password2': 'different123',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(email='juan@example.com').exists())

    def test_signup_creates_user_with_seller_role(self):
        response = self.client.post(
            reverse('signup'),
            data={
                'nombre': 'Maria',
                'apellidos': 'Lopez',
                'email': 'maria@example.com',
                'telefono': '622222222',
                'direccion': 'Avenida Venta 10',
                'ciudad': 'Barcelona',
                'codigo_postal': '08001',
                'rol': User.Role.SELLER,
                'password1': 'secret123',
                'password2': 'secret123',
            },
        )

        self.assertEqual(response.status_code, 302)
        user = User.objects.get(email='maria@example.com')
        self.assertEqual(user.nombre, 'Maria')
        self.assertEqual(user.rol, User.Role.SELLER)
        self.assertEqual(user.telefono, '622222222')
        self.assertTrue(user.check_password('secret123'))

    def test_signup_form_requires_email(self):
        response = self.client.post(
            reverse('signup'),
            data={
                'nombre': 'Juan',
                'apellidos': 'Garcia',
                'email': '',
                'telefono': '612345678',
                'direccion': 'Calle Test 1',
                'ciudad': 'Madrid',
                'codigo_postal': '28001',
                'rol': User.Role.BUYER,
                'password1': 'secret123',
                'password2': 'secret123',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(nombre='Juan').exists())


class SignUpFormTests(TestCase):
    def test_signup_form_hashes_password(self):
        form = SignUpForm(
            data={
                'nombre': 'Laura',
                'apellidos': 'Martino',
                'email': 'laura@example.com',
                'telefono': '633333333',
                'direccion': 'Calle Laura 5',
                'ciudad': 'Valencia',
                'codigo_postal': '46001',
                'rol': User.Role.BUYER,
                'password1': 'secret123',
                'password2': 'secret123',
            }
        )

        self.assertTrue(form.is_valid())
        user = form.save()
        self.assertTrue(user.check_password('secret123'))
        self.assertEqual(user.rol, User.Role.BUYER)
        self.assertEqual(user.ciudad, 'Valencia')

    def test_signup_form_rejects_mismatched_passwords(self):
        form = SignUpForm(
            data={
                'nombre': 'Laura',
                'apellidos': 'Martino',
                'email': 'laura@example.com',
                'telefono': '633333333',
                'direccion': 'Calle Laura 5',
                'ciudad': 'Valencia',
                'codigo_postal': '46001',
                'rol': User.Role.BUYER,
                'password1': 'secret123',
                'password2': 'different123',
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn('Las contraseñas no coinciden.', form.non_field_errors())