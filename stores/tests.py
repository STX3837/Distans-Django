from decimal import Decimal
from datetime import date, timedelta

from django.test import TestCase
from django.urls import reverse
from django.core.management import call_command

from users.models import User
from .models import Tienda, VisitaTienda


class StoreMapViewTests(TestCase):
    def setUp(self):
        self.buyer = User.objects.create_user(
            email='comprador@test.com',
            password='Password123',
            nombre='Comprador',
            apellidos='Prueba',
            rol=User.Role.BUYER,
        )
        self.seller = User.objects.create_user(
            email='vendedor@test.com',
            password='Password123',
            nombre='Vendedor',
            apellidos='Prueba',
            rol=User.Role.SELLER,
        )
        self.other_seller = User.objects.create_user(
            email='vendedor2@test.com',
            password='Password123',
            nombre='Vendedor',
            apellidos='Dos',
            rol=User.Role.SELLER,
        )

    def test_map_view_filters_stores_by_location_and_radius(self):
        close_store = Tienda.objects.create(
            nombre='Tienda cercana',
            descripcion='Dentro del radio',
            direccion='Calle Mayor 1',
            latitud=Decimal('40.416800'),
            longitud=Decimal('-3.703800'),
            vendedor=self.seller,
        )
        far_store = Tienda.objects.create(
            nombre='Tienda lejana',
            descripcion='Fuera del radio',
            direccion='Calle Lejana 99',
            latitud=Decimal('41.000000'),
            longitud=Decimal('-4.000000'),
            vendedor=self.other_seller,
        )

        session = self.client.session
        session['search_latitude'] = 40.4168
        session['search_longitude'] = -3.7038
        session['search_radius_km'] = 5
        session.save()

        self.client.force_login(self.buyer)
        response = self.client.get(reverse('store_map'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, close_store.nombre)
        self.assertNotContains(response, far_store.nombre)
        self.assertContains(response, 'L.circle')
        self.assertContains(response, 'L.circleMarker')
        self.assertContains(response, 'Tu ubicación seleccionada')
        self.assertContains(response, 'storePopup')

    def test_map_shows_selected_location_without_radius(self):
        session = self.client.session
        session['guest'] = True
        session['search_latitude'] = 40.4168
        session['search_longitude'] = -3.7038
        session.save()

        response = self.client.get(reverse('store_map'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'L.circleMarker')
        self.assertContains(response, 'Tu ubicación seleccionada')

    def test_admin_can_delete_store_without_image(self):
        admin = User.objects.create_user(
            email='admin@test.com',
            password='Password123',
            nombre='Admin',
            apellidos='Prueba',
            rol=User.Role.ADMIN,
        )
        store = Tienda.objects.create(nombre='Tienda sin imagen', vendedor=self.seller)
        self.client.force_login(admin)

        response = self.client.post(reverse('store_delete_admin', kwargs={'pk': store.pk}))

        self.assertRedirects(response, reverse('store_list_admin'))
        self.assertFalse(Tienda.objects.filter(pk=store.pk).exists())

    def test_store_card_links_to_selected_store_on_map(self):
        store = Tienda.objects.create(nombre='Tienda con mapa', vendedor=self.seller)
        self.client.force_login(self.buyer)

        response = self.client.get(reverse('store_list'))

        expected_url = f'{reverse("store_map")}?tienda={store.pk}'
        self.assertContains(response, f'href="{expected_url}"')
        self.assertContains(response, 'Ver en mapa')

    def test_expired_premium_store_cannot_sell_online(self):
        store = Tienda.objects.create(
            nombre='Tienda Premium caducada',
            vendedor=self.seller,
            fecha_renovacion=date.today() - timedelta(days=1),
        )

        self.assertFalse(store.permite_compra_online)

    def test_expire_premium_stores_command_deactivates_expired_store(self):
        store = Tienda.objects.create(
            nombre='Tienda a caducar',
            vendedor=self.seller,
            fecha_renovacion=date.today() - timedelta(days=1),
        )

        call_command('expire_premium_stores')

        store.refresh_from_db()
        self.assertEqual(store.plan, Tienda.Plan.FREEMIUM)
        self.assertFalse(store.suscripcion_activa)
        self.assertFalse(store.pasarela_activa)


class SellerStoreCreationTests(TestCase):
    def setUp(self):
        self.seller = User.objects.create_user(
            email='nuevo-vendedor@test.com',
            password='Password123',
            nombre='Nuevo',
            apellidos='Vendedor',
            rol=User.Role.SELLER,
        )
        self.buyer = User.objects.create_user(
            email='comprador-sin-tienda@test.com',
            password='Password123',
            nombre='Comprador',
            apellidos='Prueba',
            rol=User.Role.BUYER,
        )

    def test_seller_home_offers_store_creation_when_store_is_missing(self):
        self.client.force_login(self.seller)

        response = self.client.get(reverse('seller_home'))

        self.assertContains(response, 'Crear mi tienda')
        self.assertContains(response, reverse('store_create_seller'))

    def test_seller_can_create_own_freemium_store(self):
        self.client.force_login(self.seller)

        response = self.client.post(reverse('store_create_seller'), data={
            'nombre': 'Mi nueva tienda',
            'descripcion': 'Tienda creada por el vendedor',
            'direccion': 'Calle Mayor 10',
            'horario': 'Lunes a viernes, 09:00-20:00',
            'informacion_apertura': '',
            'latitud': '40.416800',
            'longitud': '-3.703800',
        })

        store = Tienda.objects.get(vendedor=self.seller)
        self.assertRedirects(response, reverse('store_detail', kwargs={'pk': store.pk}))
        self.assertEqual(store.plan, Tienda.Plan.FREEMIUM)
        self.assertFalse(store.suscripcion_activa)
        self.assertFalse(store.pasarela_activa)

    def test_seller_cannot_create_a_second_store(self):
        store = Tienda.objects.create(nombre='Tienda existente', vendedor=self.seller)
        self.client.force_login(self.seller)

        response = self.client.get(reverse('store_create_seller'))

        self.assertRedirects(response, reverse('store_detail', kwargs={'pk': store.pk}))
        self.assertEqual(Tienda.objects.filter(vendedor=self.seller).count(), 1)

    def test_buyer_cannot_create_store(self):
        self.client.force_login(self.buyer)

        response = self.client.get(reverse('store_create_seller'))

        self.assertRedirects(response, reverse('account_detail'))


class AdminStoreSellerSelectionTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            email='admin-tiendas@test.com',
            password='Password123',
            nombre='Admin',
            apellidos='Tiendas',
        )
        self.available_seller = User.objects.create_user(
            email='vendedor-disponible@test.com',
            password='Password123',
            nombre='Vendedor',
            apellidos='Disponible',
            rol=User.Role.SELLER,
        )
        self.assigned_seller = User.objects.create_user(
            email='vendedor-asignado@test.com',
            password='Password123',
            nombre='Vendedor',
            apellidos='Asignado',
            rol=User.Role.SELLER,
        )
        self.assigned_store = Tienda.objects.create(
            nombre='Tienda ya asignada',
            vendedor=self.assigned_seller,
        )
        self.client.force_login(self.admin)

    def test_admin_store_form_only_lists_sellers_without_store(self):
        response = self.client.get(reverse('store_create_admin'))

        seller_field = response.context['form'].fields['vendedor']
        seller_queryset = seller_field.queryset
        self.assertQuerySetEqual(seller_queryset, [self.available_seller])
        self.assertEqual(
            seller_field.label_from_instance(self.available_seller),
            self.available_seller.email,
        )
        self.assertContains(response, '<select name="vendedor"', html=False)
        self.assertContains(response, self.available_seller.email)

    def test_admin_can_create_store_and_assign_available_seller(self):
        response = self.client.post(reverse('store_create_admin'), data={
            'nombre': 'Tienda administrada',
            'vendedor': self.available_seller.pk,
            'descripcion': '',
            'direccion': 'Calle Mayor 1',
            'horario': '',
            'informacion_apertura': '',
            'plan': Tienda.Plan.FREEMIUM,
            'latitud': '40.416800',
            'longitud': '-3.703800',
        })

        self.assertRedirects(response, reverse('store_list_admin'))
        self.assertTrue(Tienda.objects.filter(
            nombre='Tienda administrada',
            vendedor=self.available_seller,
        ).exists())

    def test_admin_edit_form_keeps_current_seller_available(self):
        response = self.client.get(reverse('store_update_admin', args=[self.assigned_store.pk]))

        seller_queryset = response.context['form'].fields['vendedor'].queryset
        self.assertIn(self.assigned_seller, seller_queryset)
        self.assertIn(self.available_seller, seller_queryset)
        self.assertContains(response, self.assigned_seller.email)
        self.assertContains(response, self.available_seller.email)

    def test_admin_can_transfer_store_to_an_available_seller(self):
        response = self.client.post(
            reverse('store_update_admin', args=[self.assigned_store.pk]),
            data={
                'nombre': self.assigned_store.nombre,
                'vendedor': self.available_seller.pk,
                'descripcion': '',
                'direccion': '',
                'horario': '',
                'informacion_apertura': '',
                'plan': Tienda.Plan.PREMIUM,
                'suscripcion_activa': 'on',
                'pasarela_activa': 'on',
                'latitud': '40.416800',
                'longitud': '-3.703800',
            },
        )

        self.assertRedirects(response, reverse('store_list_admin'))
        self.assigned_store.refresh_from_db()
        self.assertEqual(self.assigned_store.vendedor, self.available_seller)


class StorePopularityFilterTests(TestCase):
    def _create_store(self, suffix):
        seller = User.objects.create_user(
            email=f'vendedor-popularidad-{suffix}@test.com',
            password='Password123',
            nombre='Vendedor',
            apellidos=suffix,
            rol=User.Role.SELLER,
        )
        return Tienda.objects.create(nombre=f'Tienda {suffix}', vendedor=seller)

    def test_zero_bucket_includes_zero_and_decimal_values_only(self):
        zero = self._create_store('cero')
        decimal_store = self._create_store('decimal')
        one = self._create_store('uno')
        for index in range(4):
            VisitaTienda.objects.create(tienda=decimal_store, session_key=f'decimal-{index}')
        for index in range(2):
            VisitaTienda.objects.create(tienda=one, session_key=f'one-{index}')
        session = self.client.session
        session['guest'] = True
        session.save()

        response = self.client.get(reverse('store_list'), {'popularidad_min': '0'})
        store_ids = {store.pk for store in response.context['stores']}

        self.assertEqual(store_ids, {zero.pk, decimal_store.pk})
        self.assertContains(response, 'step="1"')
