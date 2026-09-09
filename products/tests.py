from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import stripe
from django.test import TestCase
from django.urls import reverse

from stores.models import Tienda, VisitaTienda
from users.models import User

from .models import Producto, VisitaProducto


class SellerMetricsTests(TestCase):
	def setUp(self):
		self.seller = User.objects.create_user(
			email='vendedor-metricas@test.com',
			password='Password123',
			nombre='Vendedor',
			apellidos='Metricas',
			rol=User.Role.SELLER,
		)
		self.store = Tienda.objects.create(nombre='Tienda métricas', vendedor=self.seller)
		self.product = Producto.objects.create(
			nombre='Producto métricas',
			descripcion='Producto de prueba',
			precio=Decimal('10.00'),
			marca='Marca',
			categoria='hogar_bricolaje',
			tienda=self.store,
		)
		VisitaTienda.objects.create(tienda=self.store, session_key='guest-store')
		VisitaProducto.objects.create(producto=self.product, session_key='guest-product')

	def test_seller_home_shows_store_and_product_views(self):
		self.client.force_login(self.seller)

		response = self.client.get(reverse('seller_home'))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, '<strong>1</strong> visualizaciones de la tienda', html=True)
		self.assertContains(response, '<strong>1</strong> visualizaciones de productos', html=True)
		self.assertContains(response, 'Actividad de los últimos 7 días')
		self.assertContains(response, self.product.nombre)

	def test_guest_can_visit_store_and_product_in_sequence(self):
		session = self.client.session
		session['guest'] = True
		session.save()

		self.client.get(reverse('store_products', kwargs={'pk': self.store.pk}))
		self.client.get(reverse('product_detail', kwargs={'pk': self.product.pk}))

		self.assertEqual(VisitaTienda.objects.filter(tienda=self.store).count(), 2)
		self.assertEqual(VisitaProducto.objects.filter(producto=self.product).count(), 2)


class PremiumCheckoutTests(TestCase):
	def test_premium_checkout_uses_monthly_price(self):
		seller = User.objects.create_user(
			email='vendedor-premium@test.com',
			password='Password123',
			nombre='Vendedor',
			apellidos='Premium',
			rol=User.Role.SELLER,
		)
		Tienda.objects.create(nombre='Tienda freemium', vendedor=seller, plan=Tienda.Plan.FREEMIUM)
		self.client.force_login(seller)

		with patch('orders.views.create_premium_checkout_session') as create_session:
			create_session.return_value.url = 'https://checkout.stripe.com/test-premium'
			response = self.client.get(reverse('premium_checkout'))

		self.assertRedirects(response, 'https://checkout.stripe.com/test-premium', fetch_redirect_response=False)
		line_item = create_session.call_args.args[1]
		self.assertEqual(line_item.vendedor, seller)

	@patch('orders.views.get_stripe_session')
	def test_premium_success_accepts_stripe_object_metadata(self, get_session):
		seller = User.objects.create_user(
			email='vendedor-confirmacion@test.com',
			password='Password123',
			nombre='Vendedor',
			apellidos='Confirmacion',
			rol=User.Role.SELLER,
		)
		store = Tienda.objects.create(nombre='Tienda confirmacion', vendedor=seller, plan=Tienda.Plan.FREEMIUM)
		get_session.return_value = SimpleNamespace(
			payment_status='paid',
			metadata=stripe.StripeObject.construct_from({
				'tipo': 'suscripcion_premium',
				'tienda_id': str(store.pk),
			}, None),
		)
		self.client.force_login(seller)

		response = self.client.get(reverse('premium_checkout_success'), {'session_id': 'cs_test'})

		self.assertRedirects(response, reverse('seller_home'))
		store.refresh_from_db()
		self.assertEqual(store.plan, Tienda.Plan.PREMIUM)
