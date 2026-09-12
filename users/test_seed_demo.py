from io import StringIO
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.test import TestCase, override_settings
from products.models import Producto, VisitaProducto
from stores.models import Tienda, VisitaTienda
from orders.models import Pedido
from users.models import User, Favorite
from carts.models import Carrito, ProductoCarrito


class SeedDemoTests(TestCase):
    def test_demo_is_repeatable_and_preserves_changes(self):
        with TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            call_command('seed_demo', stdout=StringIO())
            self.assertEqual(User.objects.count(), 11)
            self.assertEqual(Tienda.objects.count(), 8)
            self.assertEqual(Producto.objects.count(), 24)
            self.assertEqual(Tienda.objects.filter(ubicacion='Sevilla').count(), 3)
            self.assertEqual(Pedido.objects.count(), 5)
            buyer = User.objects.get(email='comprador@demo.example.com')
            self.assertTrue(buyer.check_password('DemoDistans2026!'))
            admin = User.objects.get(email='admin@demo.example.com')
            self.assertTrue(admin.is_staff and admin.is_superuser)
            self.assertEqual(Tienda.objects.filter(plan='premium').count(), 5)
            for product in Producto.objects.all():
                self.assertTrue(product.imagen.storage.exists(product.imagen.name))
                self.assertGreaterEqual(product.stock, 0)
            for order in Pedido.objects.prefetch_related('items'):
                self.assertEqual(order.total, order.subtotal - order.descuento + order.impuesto + order.coste_entrega)
                self.assertEqual(sum(item.total for item in order.items.all()), order.subtotal - order.descuento)
                if order.metodo_pago == 'contrarrembolso':
                    self.assertEqual(order.estado_pago, 'cobro_tienda')
            product = Producto.objects.get(nombre='Novela de aventuras')
            product.stock = 42
            product.save()
            buyer.set_password('ChangedPassword!')
            buyer.save()
            counts = [model.objects.count() for model in [User, Tienda, Producto, Pedido, VisitaProducto, VisitaTienda, Favorite, Carrito, ProductoCarrito]]
            call_command('seed_demo', stdout=StringIO())
            self.assertEqual(counts, [model.objects.count() for model in [User, Tienda, Producto, Pedido, VisitaProducto, VisitaTienda, Favorite, Carrito, ProductoCarrito]])
            product.refresh_from_db()
            buyer.refresh_from_db()
            self.assertEqual(product.stock, 42)
            self.assertTrue(buyer.check_password('ChangedPassword!'))
