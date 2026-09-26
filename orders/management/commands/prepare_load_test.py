"""Prepara datos pequeños y repetibles para el escenario de escritura."""

from decimal import Decimal
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from orders.models import Pedido, ProductoPedido, Subpedido
from products.models import Producto
from users.models import User


class Command(BaseCommand):
    help = 'Crea o restablece los pedidos aislados de la prueba de carga write.'

    @transaction.atomic
    def handle(self, *args, **options):
        seller = User.objects.filter(email='libreria@demo.example.com').first()
        buyer = User.objects.filter(email='comprador@demo.example.com').first()
        store = getattr(seller, 'tienda', None) if seller else None
        product = Producto.objects.filter(tienda=store).order_by('pk').first() if store else None
        if not buyer or not store or not product:
            raise CommandError('Faltan datos. Ejecuta primero: python manage.py seed_demo')

        # Limpia restos de una ejecución interrumpida antes de preparar la siguiente.
        Producto.objects.filter(nombre__startswith='LOADTEST-', tienda=store).delete()

        for index in range(1, 11):
            code = f'LOAD-WRITE-{index:03d}'
            order, _ = Pedido.objects.update_or_create(codigo_pedido=code, defaults={
                'usuario': buyer, 'estado': 'preparacion', 'comprador_nombre': 'Carga',
                'comprador_apellidos': 'Controlada', 'comprador_email': 'carga@example.invalid',
                'telefono': '600000000', 'subtotal': Decimal('10.00'),
                'descuento': Decimal('0.00'), 'impuesto': Decimal('2.10'),
                'coste_entrega': Decimal('0.00'), 'total': Decimal('12.10'),
                'metodo_pago': 'contrarrembolso', 'estado_pago': 'cobro_tienda',
                'direccion_envio': 'Calle Carga 1', 'ciudad_envio': 'Madrid',
                'codigo_postal_envio': '28001', 'direccion_facturacion': 'Calle Carga 1',
                'ciudad_facturacion': 'Madrid', 'codigo_postal_facturacion': '28001',
                'stock_reservado': False, 'stock_descontado': False,
            })
            suborder, _ = Subpedido.objects.update_or_create(
                pedido=order, tienda=store,
                defaults={'nombre_tienda': store.nombre, 'estado': 'preparacion'},
            )
            ProductoPedido.objects.update_or_create(pedido=order, producto=product, defaults={
                'subpedido': suborder, 'tienda': store, 'nombre_producto': product.nombre,
                'nombre_tienda': store.nombre, 'cantidad': 1,
                'precio_unitario': Decimal('10.00'), 'total': Decimal('10.00'),
                'cancelado': False, 'cancelado_at': None,
            })

        self.stdout.write(self.style.SUCCESS(
            'Prueba write preparada: 10 pedidos LOAD-WRITE restablecidos.'
        ))
