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
		self.assertEqual(pedido.estado, 'preparacion')
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


class CheckoutFormValidationTests(TestCase):
	def test_buyer_form_rejects_invalid_personal_data(self):
		form = CheckoutBuyerForm(
			data={
				'nombre': 'Ana123',
				'apellidos': 'Pérez',
				'email': 'correo-no-valido',
				'telefono': 'abc',
			}
		)

		self.assertFalse(form.is_valid())
		self.assertIn('nombre', form.errors)
		self.assertIn('email', form.errors)
		self.assertIn('telefono', form.errors)

	def test_buyer_form_normalizes_valid_data(self):
		form = CheckoutBuyerForm(
			data={
				'nombre': '  Ana  ',
				'apellidos': '  Pérez   Gómez ',
				'email': 'ana@example.com',
				'telefono': '+34 600 123 123',
			}
		)

		self.assertTrue(form.is_valid())
		self.assertEqual(form.cleaned_data['nombre'], 'Ana')
		self.assertEqual(form.cleaned_data['apellidos'], 'Pérez Gómez')
		self.assertEqual(form.cleaned_data['telefono'], '+34600123123')

	def test_address_form_rejects_invalid_shipping_data(self):
		form = CheckoutAddressForm(
			data={
				'direccion_envio': '---',
				'ciudad_envio': 'Madrid22',
				'codigo_postal_envio': '99999',
				'direccion_facturacion': 'Calle Falsa',
				'ciudad_facturacion': 'Sevilla',
				'codigo_postal_facturacion': '41001',
			}
		)

		self.assertFalse(form.is_valid())
		self.assertIn('direccion_envio', form.errors)
		self.assertIn('ciudad_envio', form.errors)
		self.assertIn('codigo_postal_envio', form.errors)

	def test_address_form_accepts_and_normalizes_valid_data(self):
		form = CheckoutAddressForm(
			data={
				'direccion_envio': '  Calle Mayor   1  ',
				'ciudad_envio': '  Madrid ',
				'codigo_postal_envio': '28001',
				'direccion_facturacion': ' Avenida de la Constitución 25 ',
				'ciudad_facturacion': ' Sevilla ',
				'codigo_postal_facturacion': '41001',
			}
		)

		self.assertTrue(form.is_valid())
		self.assertEqual(form.cleaned_data['direccion_envio'], 'Calle Mayor 1')
		self.assertEqual(form.cleaned_data['ciudad_envio'], 'Madrid')
		self.assertEqual(form.cleaned_data['direccion_facturacion'], 'Avenida de la Constitución 25')
		self.assertEqual(form.cleaned_data['ciudad_facturacion'], 'Sevilla')

class OrderTrackingAndManagementTests(TestCase):
    def setUp(self):
        self.vendor = User.objects.create_user(
            email='vendedor2@example.com',
            password='password123',
            nombre='Vendedor',
            apellidos='Demo',
            rol=User.Role.SELLER,
        )
        self.store = Tienda.objects.create(nombre='Tienda Tracking', vendedor=self.vendor)
        self.product = Producto.objects.create(
            nombre='Producto tracking',
            descripcion='Descripción',
            precio=Decimal('50.00'),
            marca='Marca',
            categoria='tecnologia_electronica',
            stock=5,
            tienda=self.store,
        )

    def test_checkout_marks_order_in_preparation(self):
        session = self.client.session
        session['guest'] = True
        session['cart'] = {
            str(self.product.pk): {
                'id': self.product.pk,
                'nombre': self.product.nombre,
                'precio': '50.00',
                'precio_oferta': '',
                'en_oferta': False,
                'porcentaje_descuento': '0',
                'imagen': '',
                'cantidad': 1,
                'tienda_id': self.store.pk,
                'tienda_nombre': self.store.nombre,
            }
        }
        session.save()

        self.client.get(reverse('checkout_customer'))
        self.client.post(
            reverse('checkout_customer'),
            {'nombre': 'Ana', 'apellidos': 'Pérez', 'email': 'ana@example.com', 'telefono': '600123123'}
        )
        self.client.post(
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
        response = self.client.post(reverse('checkout_payment'), {'metodo_pago': 'pasarela'})

        self.assertRedirects(response, reverse('checkout_complete'))
        pedido = Pedido.objects.get()
        self.assertEqual(pedido.estado, 'preparacion')
        self.assertEqual(pedido.get_estado_display(), 'En preparación')

    def test_guest_can_access_order_history_and_lookup_by_code(self):
        session = self.client.session
        session['guest'] = True
        session['guest_order_codes'] = ['PED-TEST-01']
        session.save()

        Pedido.objects.create(
            codigo_pedido='PED-TEST-01',
            comprador_nombre='Ana',
            comprador_apellidos='Pérez',
            comprador_email='ana@example.com',
            telefono='600123123',
            subtotal=Decimal('50.00'),
            impuesto=Decimal('10.50'),
            coste_entrega=Decimal('0.00'),
            total=Decimal('60.50'),
            metodo_pago='pasarela',
            direccion_envio='Calle Mayor 1',
            ciudad_envio='Madrid',
            codigo_postal_envio='28001',
            direccion_facturacion='Calle Mayor 1',
            ciudad_facturacion='Madrid',
            codigo_postal_facturacion='28001',
            estado='preparacion',
        )

        response = self.client.get(reverse('order_history'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Mis pedidos')
        self.assertContains(response, 'buscar por código')
        self.assertContains(response, 'PED-TEST-01')

        response = self.client.post(reverse('order_lookup'), {'codigo_pedido': 'ped-test-01'})
        self.assertRedirects(response, reverse('order_detail', args=['PED-TEST-01']))

    def test_vendor_can_view_and_filter_orders(self):
        self.client.force_login(self.vendor)
        pedido = Pedido.objects.create(
            codigo_pedido='PED-VENDOR-01',
            usuario=self.vendor,
            comprador_nombre='Comprador',
            comprador_apellidos='Prueba',
            comprador_email='comprador@example.com',
            telefono='600000001',
            subtotal=Decimal('100.00'),
            impuesto=Decimal('21.00'),
            coste_entrega=Decimal('0.00'),
            total=Decimal('121.00'),
            metodo_pago='pasarela',
            direccion_envio='Calle Falsa 1',
            ciudad_envio='Madrid',
            codigo_postal_envio='28001',
            direccion_facturacion='Calle Falsa 1',
            ciudad_facturacion='Madrid',
            codigo_postal_facturacion='28001',
            estado='preparacion',
        )
        pedido.items.create(
            producto=self.product,
            cantidad=2,
            precio_unitario=Decimal('50.00'),
            total=Decimal('100.00'),
        )

        response = self.client.get(reverse('vendor_order_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'PED-VENDOR-01')
        self.assertContains(response, 'Comprador')

        response = self.client.get(reverse('vendor_order_list'), {'codigo_pedido': 'PED-VENDOR-01'})
        self.assertContains(response, 'PED-VENDOR-01')

        response = self.client.get(reverse('vendor_order_list'), {'usuario': 'comprador@example.com'})
        self.assertContains(response, 'PED-VENDOR-01')

    def test_vendor_order_list_filters_by_selected_store(self):
        other_vendor = User.objects.create_user(
            email='otro_vendedor@example.com',
            password='password123',
            nombre='Otro',
            apellidos='Vendedor',
            rol=User.Role.SELLER,
        )
        other_store = Tienda.objects.create(nombre='Tienda Otras', vendedor=other_vendor)
        other_product = Producto.objects.create(
            nombre='Producto ajeno',
            descripcion='Otro',
            precio=Decimal('90.00'),
            marca='Marca',
            categoria='tecnologia_electronica',
            stock=10,
            tienda=other_store,
        )

        store_order = Pedido.objects.create(
            codigo_pedido='PED-STORE-OK',
            usuario=self.vendor,
            comprador_nombre='A',
            comprador_apellidos='B',
            comprador_email='a@b.com',
            telefono='600000002',
            subtotal=Decimal('50.00'),
            impuesto=Decimal('10.50'),
            coste_entrega=Decimal('0.00'),
            total=Decimal('60.50'),
            metodo_pago='pasarela',
            direccion_envio='Calle 1',
            ciudad_envio='Madrid',
            codigo_postal_envio='28001',
            direccion_facturacion='Calle 1',
            ciudad_facturacion='Madrid',
            codigo_postal_facturacion='28001',
            estado='preparacion',
        )
        store_order.items.create(
            producto=self.product,
            cantidad=1,
            precio_unitario=Decimal('50.00'),
            total=Decimal('50.00'),
        )

        other_order = Pedido.objects.create(
            codigo_pedido='PED-STORE-OTHER',
            usuario=other_vendor,
            comprador_nombre='C',
            comprador_apellidos='D',
            comprador_email='c@d.com',
            telefono='600000003',
            subtotal=Decimal('90.00'),
            impuesto=Decimal('18.90'),
            coste_entrega=Decimal('0.00'),
            total=Decimal('108.90'),
            metodo_pago='pasarela',
            direccion_envio='Calle 2',
            ciudad_envio='Madrid',
            codigo_postal_envio='28001',
            direccion_facturacion='Calle 2',
            ciudad_facturacion='Madrid',
            codigo_postal_facturacion='28001',
            estado='enviado',
        )
        other_order.items.create(
            producto=other_product,
            cantidad=1,
            precio_unitario=Decimal('90.00'),
            total=Decimal('90.00'),
        )

        self.client.force_login(self.vendor)
        response = self.client.get(reverse('vendor_order_list'), {'tienda': self.store.pk})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'PED-STORE-OK')
        self.assertNotContains(response, 'PED-STORE-OTHER')