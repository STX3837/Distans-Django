from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from users.models import User
from .models import Tienda


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
