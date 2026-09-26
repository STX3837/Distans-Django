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
        self.assertContains(response, 'storePopup')

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
