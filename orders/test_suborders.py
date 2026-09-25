from decimal import Decimal

from django.test import TestCase

from products.models import Producto
from stores.models import Tienda
from users.models import User

from .models import Subpedido
from .utils import cancel_suborder, create_order_from_checkout, sync_order_status


class SuborderWorkflowTests(TestCase):
    def setUp(self):
        self.vendors = [
            User.objects.create_user(
                email=f'vendor{index}@example.com', password='test', nombre='Vendor',
                apellidos=str(index), rol=User.Role.SELLER,
            )
            for index in (1, 2)
        ]
        self.stores = [
            Tienda.objects.create(nombre=f'Tienda {index}', vendedor=vendor)
            for index, vendor in enumerate(self.vendors, 1)
        ]
        self.products = [
            Producto.objects.create(
                nombre=f'Producto {index}', descripcion='Test', precio=price,
                marca='Marca', categoria='hogar_bricolaje', stock=5, tienda=store,
            )
            for index, (price, store) in enumerate(
                zip((Decimal('10.00'), Decimal('20.00')), self.stores), 1
            )
        ]

    def create_order(self):
        items = []
        for product in self.products:
            items.append({
                'producto': product,
                'cantidad': 1,
                'precio_unitario': product.precio,
                'subtotal_neto': product.precio,
            })
        return create_order_from_checkout(
            user=None,
            buyer_data={'nombre': 'Buyer', 'apellidos': 'Test', 'email': 'buyer@example.com', 'telefono': '600000000'},
            address_data={
                'direccion_envio': 'Calle 1', 'ciudad_envio': 'Madrid', 'codigo_postal_envio': '28001',
                'direccion_facturacion': 'Calle 1', 'ciudad_facturacion': 'Madrid', 'codigo_postal_facturacion': '28001',
            },
            payment_method='contrarrembolso',
            cart_snapshot={
                'items': items, 'physical_only_items': [], 'subtotal': Decimal('30.00'),
                'descuento': Decimal('0.00'), 'impuesto': Decimal('6.30'),
                'coste_entrega': Decimal('0.00'), 'total': Decimal('36.30'),
            },
        )

    def test_checkout_creates_one_suborder_per_store(self):
        order = self.create_order()
        self.assertEqual(order.subpedidos.count(), 2)
        self.assertEqual(order.items.filter(subpedido__isnull=False).count(), 2)

    def test_cancel_one_suborder_keeps_history_restores_its_stock_and_recalculates(self):
        order = self.create_order()
        cancelled = order.subpedidos.get(tienda=self.stores[0])

        self.assertTrue(cancel_suborder(cancelled))

        order.refresh_from_db()
        cancelled.refresh_from_db()
        self.products[0].refresh_from_db()
        self.products[1].refresh_from_db()
        self.assertEqual(cancelled.estado, 'cancelado')
        self.assertTrue(cancelled.items.get().cancelado)
        self.assertEqual(self.products[0].stock, 5)
        self.assertEqual(self.products[1].stock, 4)
        self.assertEqual(order.subtotal, Decimal('20.00'))
        self.assertEqual(order.impuesto, Decimal('4.20'))
        self.assertEqual(order.total, Decimal('24.20'))
        self.assertEqual(order.estado, 'preparacion')

    def test_buyer_order_becomes_sent_only_when_all_active_suborders_are_collected(self):
        order = self.create_order()
        first, second = list(order.subpedidos.all())
        first.estado = 'recogido'
        first.save(update_fields=['estado'])
        self.assertEqual(sync_order_status(order), 'preparacion')
        second.estado = 'recogido'
        second.save(update_fields=['estado'])
        self.assertEqual(sync_order_status(order), 'enviado')

