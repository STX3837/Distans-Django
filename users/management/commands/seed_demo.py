"""Create a repeatable, offline demonstration without calling payment services."""
from datetime import timedelta
from decimal import Decimal
from io import BytesIO
from types import SimpleNamespace

from PIL import Image, ImageDraw
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from carts.models import Carrito, ProductoCarrito
from orders.models import Pedido
from orders.utils import build_cart_snapshot, create_order_from_checkout, mark_order_as_paid, release_order_stock_reservation
from products.models import Producto, VisitaProducto
from stores.models import Tienda, VisitaTienda
from users.models import Favorite, User


PASSWORD = 'DemoDistans2026!'
STORES = [
    ('libreria', 'Librería Horizonte Demo', '40.416800', '-3.703800', 'Calle Demo 1', True),
    ('tecnologia', 'Tecnología Centro Demo', '40.420000', '-3.700000', 'Calle Demo 2', True),
    ('jardin', 'Jardín del Barrio Demo', '40.430000', '-3.710000', 'Calle Demo 3', False),
    ('mercado', 'Mercado Artesano Demo', '40.460000', '-3.690000', 'Calle Demo 4', True),
    ('hogar', 'Hogar Alcalá Demo', '40.481000', '-3.364000', 'Calle Demo 5', False),
    ('sevilla-triana', 'Artesanía Triana Demo', '37.383000', '-6.003000', 'Calle Demo Triana 1', True),
    ('sevilla-centro', 'Librería Sevilla Centro Demo', '37.389100', '-5.984500', 'Calle Demo Centro 2', True),
    ('sevilla-nervion', 'Flores Nervión Demo', '37.382500', '-5.970000', 'Calle Demo Nervión 3', False),
]
PRODUCTS = [
    ('libreria', 'Novela de aventuras', 'cultura_ocio', '18.00', '14.00', 25),
    ('libreria', 'Juego de mesa familiar', 'cultura_ocio', '32.00', None, 12),
    ('libreria', 'Cuaderno de notas', 'papeleria_oficina', '6.50', None, 40),
    ('tecnologia', 'Auriculares inalámbricos', 'tecnologia_electronica', '49.90', '39.90', 20),
    ('tecnologia', 'Teclado compacto', 'tecnologia_electronica', '29.90', None, 10),
    ('tecnologia', 'Ratón agotado', 'tecnologia_electronica', '15.00', None, 0),
    ('jardin', 'Planta de interior', 'floristeria_jardineria', '12.00', None, 18),
    ('jardin', 'Ramo de flores', 'floristeria_jardineria', '25.00', '20.00', 8),
    ('jardin', 'Maceta de cerámica', 'hogar_bricolaje', '9.50', None, 15),
    ('mercado', 'Cesta de productos artesanos', 'alimentacion_bebidas', '24.00', '21.00', 20),
    ('mercado', 'Bolsa de tela', 'moda_complementos', '8.00', None, 30),
    ('mercado', 'Jabón artesanal', 'salud_bienestar', '5.00', None, 35),
    ('hogar', 'Lámpara de escritorio', 'hogar_bricolaje', '35.00', None, 10),
    ('hogar', 'Kit de herramientas', 'hogar_bricolaje', '42.00', None, 7),
    ('hogar', 'Organizador no disponible', 'papeleria_oficina', '11.00', None, 5),
    ('sevilla-triana', 'Azulejo decorativo', 'hogar_bricolaje', '18.00', '15.00', 20),
    ('sevilla-triana', 'Abanico artesanal', 'moda_complementos', '22.00', None, 15),
    ('sevilla-triana', 'Taza de cerámica sevillana', 'hogar_bricolaje', '12.00', None, 25),
    ('sevilla-centro', 'Guía de paseos por Sevilla', 'cultura_ocio', '16.50', '13.50', 30),
    ('sevilla-centro', 'Cuaderno ilustrado', 'papeleria_oficina', '7.50', None, 40),
    ('sevilla-centro', 'Juego de cartas', 'cultura_ocio', '9.00', None, 18),
    ('sevilla-nervion', 'Ramo de temporada', 'floristeria_jardineria', '28.00', '24.00', 12),
    ('sevilla-nervion', 'Planta aromática', 'floristeria_jardineria', '6.00', None, 20),
    ('sevilla-nervion', 'Jardinera de balcón', 'hogar_bricolaje', '19.00', None, 10),
]


class Command(BaseCommand):
    help = 'Crea usuarios, tiendas, productos, pedidos y estadísticas ficticios sin duplicarlos.'

    def image(self, field, name, label, color):
        storage = field.storage
        path = f'demo/{name}.png'
        if not storage.exists(path):
            canvas = Image.new('RGB', (640, 420), color)
            draw = ImageDraw.Draw(canvas)
            draw.rounded_rectangle((60, 60, 580, 360), radius=25, fill='#ffffff')
            draw.text((90, 150), 'DISTANS DEMO', fill='#173b35')
            draw.text((90, 195), label, fill='#173b35')
            data = BytesIO()
            canvas.save(data, format='PNG')
            path = storage.save(path, ContentFile(data.getvalue()))
        field.name = path

    def user(self, email, role, name, admin=False, city='Madrid'):
        user, created = User.objects.get_or_create(email=email, defaults={
            'nombre': name, 'apellidos': 'Demostración', 'rol': role,
            'telefono': '600123123', 'direccion': 'Calle Demo 10',
            'ciudad': city, 'codigo_postal': '41001' if city == 'Sevilla' else '28001', 'is_superuser': admin,
        })
        if not created and (user.rol != role or admin and not user.is_superuser):
            raise CommandError(f'La cuenta {email} ya existe con otro rol. No se ha modificado.')
        if created:
            user.set_password(PASSWORD)
            user.save()
        return user

    @transaction.atomic
    def handle(self, *args, **options):
        self.user('admin@demo.example.com', User.Role.ADMIN, 'Admin', admin=True)
        buyer = self.user('comprador@demo.example.com', User.Role.BUYER, 'Ana')
        second_buyer = self.user('comprador2@demo.example.com', User.Role.BUYER, 'Luis')
        stores = {}
        for slug, name, lat, lng, address, premium in STORES:
            city = 'Sevilla' if slug.startswith('sevilla-') else ('Alcalá de Henares' if slug == 'hogar' else 'Madrid')
            seller = self.user(f'{slug}@demo.example.com', User.Role.SELLER, name, city=city)
            store, created = Tienda.objects.get_or_create(vendedor=seller, defaults={
                'nombre': name, 'descripcion': 'Comercio ficticio para probar DISTANS.',
                'direccion': address, 'ubicacion': city,
                'latitud': Decimal(lat), 'longitud': Decimal(lng),
                'horario': 'Lunes a viernes, 09:00–20:00',
                'informacion_apertura': 'Datos ficticios de demostración.',
                'plan': Tienda.Plan.PREMIUM if premium else Tienda.Plan.FREEMIUM,
                'suscripcion_activa': premium, 'pasarela_activa': premium,
                # Local demo Premium: no fake Stripe subscription identifiers.
                'fecha_renovacion': None,
            })
            if created or not store.imagen:
                self.image(store.imagen, slug, name, '#b9ddcf')
                store.save(update_fields=['imagen'])
            stores[slug] = store

        products = []
        for index, (slug, name, category, price, offer, stock) in enumerate(PRODUCTS):
            product, created = Producto.objects.get_or_create(tienda=stores[slug], nombre=name, defaults={
                'descripcion': f'{name}. Producto ficticio para la demostración.',
                'precio': Decimal(price), 'precio_oferta': Decimal(offer) if offer else None,
                'en_oferta': bool(offer), 'categoria': category, 'marca': 'DISTANS Demo',
                'stock': stock, 'disponible': name != 'Organizador no disponible',
                'destacado': index % 3 == 0,
            })
            if created or not product.imagen:
                self.image(product.imagen, f'producto-{index + 1}', name, '#c6d9ed')
                product.save(update_fields=['imagen'])
            products.append(product)

        address = {f'{field}_{suffix}': value for suffix in ('envio', 'facturacion')
                   for field, value in [('direccion', buyer.direccion), ('ciudad', buyer.ciudad), ('codigo_postal', buyer.codigo_postal)]}
        for index, state in enumerate(['preparacion', 'enviado', 'entregado', 'preparacion', 'cancelado']):
            code = f'PED-DEMO-{index + 1:03d}'
            if Pedido.objects.filter(codigo_pedido=code).exists():
                continue
            customer = buyer if index % 2 == 0 else second_buyer
            product = products[0] if index < 3 else products[3]
            method = 'contrarrembolso' if index < 3 else 'pasarela'
            snapshot = build_cart_snapshot(SimpleNamespace(user=SimpleNamespace(is_authenticated=False), session={
                'cart': {str(product.pk): {'id': product.pk, 'cantidad': 1}},
            }))
            order = create_order_from_checkout(user=customer,
                buyer_data={'nombre': customer.nombre, 'apellidos': customer.apellidos, 'email': customer.email, 'telefono': customer.telefono},
                address_data=address, payment_method=method, cart_snapshot=snapshot)
            if method == 'pasarela' and state != 'cancelado':
                mark_order_as_paid(order)  # Fictitious payment; no Stripe request.
            if state == 'cancelado':
                release_order_stock_reservation(order)
            order.refresh_from_db()
            order.codigo_pedido = code
            order.estado = state
            order.fecha = timezone.localdate() - timedelta(days=index)
            order.save()

        cart, _ = Carrito.objects.get_or_create(usuario=buyer)
        ProductoCarrito.objects.get_or_create(carrito=cart, producto=products[1], defaults={'cantidad': 2})
        Favorite.objects.get_or_create(usuario=buyer, producto=products[0])
        Favorite.objects.get_or_create(usuario=buyer, tienda=stores['jardin'])
        for index, product in enumerate(products):
            for visit in range(3):
                key = f'demo:product:{index}:{visit}'
                record, created = VisitaProducto.objects.get_or_create(producto=product, session_key=key)
                if created:
                    VisitaProducto.objects.filter(pk=record.pk).update(created_at=timezone.now() - timedelta(days=visit))
        for slug, store in stores.items():
            for visit in range(7):
                record, created = VisitaTienda.objects.get_or_create(tienda=store, session_key=f'demo:store:{slug}:{visit}')
                if created:
                    VisitaTienda.objects.filter(pk=record.pk).update(created_at=timezone.now() - timedelta(days=visit))
        self.stdout.write(self.style.SUCCESS(f'Demo preparada: {len(STORES) + 3} usuarios, {len(STORES)} tiendas, {len(PRODUCTS)} productos y 5 pedidos de ejemplo.'))
        self.stdout.write(f'Contraseña inicial de las cuentas nuevas: {PASSWORD}')
        self.stdout.write('Comprador: comprador@demo.example.com | Admin: admin@demo.example.com')
        self.stdout.write('Vendedores: ' + ', '.join(store[0] + '@demo.example.com' for store in STORES))
        self.stdout.write('Ubicación de referencia para el mapa: Madrid (40.416800, -3.703800).')
        self.stdout.write('Sevilla: (37.389100, -5.984500), con tiendas en Centro, Triana y Nervión.')
