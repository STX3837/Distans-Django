from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import TestCase
from django.test.client import RequestFactory
from django.urls import reverse

from products.models import Producto
from stores.models import Tienda
from users.models import User

from .forms import CheckoutAddressForm, CheckoutBuyerForm
from .models import Pedido
from .utils import build_cart_snapshot


class CheckoutFlowTests(TestCase):
	def setUp(self):
		self.vendor = User.objects.create_user(
			email='vendedor@example.com',
			password='password123',
			nombre='Vendedor',
			apellidos='Demo',
			rol=User.Role.SELLER,
		)
		self.store = Tienda.objects.create(nombre='Tienda Demo', vendedor=self.vendor)
		self.product = Producto.objects.create(
			nombre='Producto oferta',
			descripcion='Descripción',
			precio=Decimal('100.00'),
			precio_oferta=Decimal('80.00'),
			en_oferta=True,
			marca='Marca',
			categoria='tecnologia_electronica',
			imagen=SimpleUploadedFile('producto.jpg', b'fake-image-bytes', content_type='image/jpeg'),
			stock=10,
			tienda=self.store,
		)

	def _set_guest_cart(self):
		session = self.client.session
		session['guest'] = True
		session['cart'] = {
			str(self.product.pk): {
				'id': self.product.pk,
				'nombre': self.product.nombre,
				'precio': str(self.product.precio),
				'precio_oferta': str(self.product.precio_oferta),
				'en_oferta': True,
				'porcentaje_descuento': str(self.product.porcentaje_descuento()),
				'imagen': '',
				'cantidad': 2,
				'tienda_id': self.store.pk,
				'tienda_nombre': self.store.nombre,
			}
		}
		session.save()

	def _build_request_with_session(self):
		request = RequestFactory().get('/carrito/')
		middleware = SessionMiddleware(lambda req: None)
		middleware.process_request(request)
		request.session = self.client.session
		request.user = type('AnonymousUserStub', (), {'is_authenticated': False})()
		request.session['guest'] = True
		request.session.save()
		return request

	def test_build_cart_snapshot_calculates_discount_and_tax(self):
		self._set_guest_cart()

		snapshot = build_cart_snapshot(self._build_request_with_session())

		self.assertEqual(snapshot['subtotal'], Decimal('200.00'))
		self.assertEqual(snapshot['descuento'], Decimal('40.00'))
		self.assertEqual(snapshot['impuesto'], Decimal('33.60'))
		self.assertEqual(snapshot['total'], Decimal('193.60'))

	def test_complete_checkout_creates_completed_order(self):
		self._set_guest_cart()

		response = self.client.get(reverse('checkout_customer'))
		self.assertEqual(response.status_code, 200)

		response = self.client.post(
			reverse('checkout_customer'),
			{
				'nombre': 'Ana',
				'apellidos': 'Pérez',
				'email': 'ana@example.com',
				'telefono': '600123123',
			},
		)
		self.assertRedirects(response, reverse('checkout_address'))

		response = self.client.post(
			reverse('checkout_address'),
			{
				'direccion_envio': 'Calle Mayor 1',
				'ciudad_envio': 'Madrid',
				'codigo_postal_envio': '28001',
				'direccion_facturacion': 'Calle Mayor 1',
				'ciudad_facturacion': 'Madrid',
				'codigo_postal_facturacion': '28001',
			},
		)
		self.assertRedirects(response, reverse('checkout_payment'))

		response = self.client.post(
			reverse('checkout_payment'),
			{'metodo_pago': 'pasarela'},
		)
		self.assertRedirects(response, reverse('checkout_complete'))

		pedido = Pedido.objects.get()
		self.assertEqual(pedido.estado, 'completado')
		self.assertEqual(pedido.total, Decimal('193.60'))
		self.assertEqual(pedido.items.count(), 1)
		self.assertEqual(pedido.items.first().precio_unitario, Decimal('80.00'))


class CheckoutFormDefaultsTests(TestCase):
	def test_registered_user_values_are_used_as_defaults(self):
		user = User.objects.create_user(
			email='comprador@example.com',
			password='password123',
			nombre='Laura',
			apellidos='Gómez',
			telefono='611111111',
			direccion='Avenida 10',
			ciudad='Sevilla',
			codigo_postal='41001',
		)

		buyer_form = CheckoutBuyerForm(user=user)
		address_form = CheckoutAddressForm(user=user)

		self.assertEqual(buyer_form.initial['nombre'], 'Laura')
		self.assertEqual(buyer_form.initial['apellidos'], 'Gómez')
		self.assertEqual(buyer_form.initial['email'], 'comprador@example.com')
		self.assertEqual(buyer_form.initial['telefono'], '611111111')
		self.assertEqual(address_form.initial['direccion_envio'], 'Avenida 10')
		self.assertEqual(address_form.initial['ciudad_facturacion'], 'Sevilla')
