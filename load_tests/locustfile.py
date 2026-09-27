"""Tres escenarios reproducibles de carga HTTP para DISTANS."""

from __future__ import annotations

import os
import random
import re
import uuid
from base64 import b64decode
from dataclasses import dataclass
from itertools import count

from locust import HttpUser, LoadTestShape, between, events, task


SCENARIO = os.getenv('LOAD_STAGES', 'baseline').lower()
VALID_SCENARIOS = {'baseline', 'stress', 'write'}
if SCENARIO not in VALID_SCENARIOS:
    raise ValueError(f"LOAD_STAGES debe ser uno de: {', '.join(sorted(VALID_SCENARIOS))}")

PASSWORD = os.getenv('LOAD_PASSWORD', 'DemoDistans2026!')
BUYER_EMAIL = os.getenv('LOAD_BUYER_EMAIL', 'comprador@demo.example.com')
SELLER_EMAIL = os.getenv('LOAD_SELLER_EMAIL', 'libreria@demo.example.com')
MAX_FAILURE_RATIO = float(os.getenv('LOAD_MAX_FAILURE_RATIO', '0.01'))
MAX_P95_MS = int(os.getenv('LOAD_MAX_P95_MS', '1200'))

PRODUCT_RE = re.compile(r'href=["\']/productos/(\d+)/["\']')
CART_PRODUCT_RE = re.compile(r'action=["\']/productos/(\d+)/agregar-carrito/["\']')
CSRF_RE = re.compile(r'name=["\']csrfmiddlewaretoken["\'] value=["\']([^"\']+)')
SELLER_STORE_RE = re.compile(r'href=["\']/vendedor/tiendas/(\d+)/["\']')
ORDER_RE = re.compile(r'href=["\']/gestion/pedidos/(LOAD-WRITE-\d+)/\?tienda=(\d+)')
ORDER_STATE_RE = re.compile(r'<option value=["\'](listo|recogido)["\']')
PNG_BYTES = b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII='
)
WRITE_USER_SEQUENCE = count()


def _ids(pattern: re.Pattern[str], html: str) -> list[int]:
    return list(dict.fromkeys(int(value) for value in pattern.findall(html)))


class DistansUser(HttpUser):
    abstract = True
    wait_time = between(1, 3)

    def csrf(self, response=None) -> str:
        if response is not None:
            match = CSRF_RE.search(response.text)
            if match:
                return match.group(1)
        return self.client.cookies.get('csrftoken', '')

    def login(self, email: str) -> None:
        login_page = self.client.get('/accounts/login/', name='GET /accounts/login/')
        with self.client.post(
            '/accounts/login/',
            {'username': email, 'password': PASSWORD, 'csrfmiddlewaretoken': self.csrf(login_page)},
            headers={'Referer': f'{self.host}/accounts/login/'},
            name='POST /accounts/login/', allow_redirects=True, catch_response=True,
        ) as response:
            if response.status_code != 200 or '/accounts/login/' in response.url:
                response.failure(f'no se pudo iniciar sesión como {email}')

    def discover_catalog(self) -> None:
        with self.client.get('/productos/', name='GET /productos/', catch_response=True) as response:
            self.product_ids = _ids(PRODUCT_RE, response.text) if response.status_code == 200 else []
            self.cart_product_ids = _ids(CART_PRODUCT_RE, response.text) if response.status_code == 200 else []
            if not self.product_ids:
                response.failure('el catálogo no contiene productos; ejecuta seed_demo')


class BrowseUser(DistansUser):
    abstract = SCENARIO == 'write'
    weight = 7

    def on_start(self):
        self.product_ids, self.cart_product_ids = [], []
        self.client.get('/accounts/guest-login/', name='GET /accounts/guest-login/', allow_redirects=True)
        self.discover_catalog()

    @task(8)
    def catalog(self):
        self.client.get('/productos/', name='GET /productos/')

    @task(4)
    def filtered_catalog(self):
        params = random.choice([
            {'categoria': 'cultura_ocio'},
            {'categoria': 'tecnologia_electronica', 'precio_max': '60'},
            {'precio_min': '5', 'precio_max': '35', 'popularidad_min': '0'},
        ])
        self.client.get('/productos/', params=params, name='GET /productos/ [filtros]')

    @task(4)
    def product_detail(self):
        if self.product_ids:
            self.client.get(f'/productos/{random.choice(self.product_ids)}/', name='GET /productos/:id/')

    @task(2)
    def stores(self):
        self.client.get('/tiendas/', name='GET /tiendas/')

    @task(2)
    def map(self):
        self.client.get('/tiendas/mapa/', name='GET /tiendas/mapa/')

    @task(1)
    def cart_flow(self):
        if not self.cart_product_ids:
            return
        product_id = random.choice(self.cart_product_ids)
        self.client.post(
            f'/productos/{product_id}/agregar-carrito/',
            {'cantidad': 1, 'csrfmiddlewaretoken': self.csrf()},
            headers={'Referer': f'{self.host}/productos/{product_id}/'},
            name='POST /productos/:id/agregar-carrito/',
        )
        self.client.get('/carrito/', name='GET /carrito/')


class BuyerUser(DistansUser):
    abstract = SCENARIO == 'write'
    weight = 2

    def on_start(self):
        self.product_ids, self.cart_product_ids = [], []
        self.login(BUYER_EMAIL)
        self.discover_catalog()

    @task(4)
    def favorites(self):
        self.client.get('/favoritos/', name='GET /favoritos/')

    @task(4)
    def order_history(self):
        self.client.get('/pedidos/mis-pedidos/', name='GET /pedidos/mis-pedidos/')

    @task(2)
    def account(self):
        self.client.get('/cuenta/', name='GET /cuenta/')

    @task(3)
    def catalog(self):
        self.client.get('/productos/', name='GET /productos/')


class SellerUser(DistansUser):
    abstract = SCENARIO == 'write'
    weight = 1

    def on_start(self):
        self.login(SELLER_EMAIL)

    @task(5)
    def dashboard(self):
        self.client.get('/vendedor/', name='GET /vendedor/')

    @task(4)
    def orders(self):
        self.client.get('/gestion/pedidos/', name='GET /gestion/pedidos/')

    @task(1)
    def filtered_orders(self):
        self.client.get('/gestion/pedidos/', params={'codigo_pedido': 'PED-DEMO'},
                        name='GET /gestion/pedidos/ [filtro]')


class WriteUser(DistansUser):
    """Un producto temporal por usuario y transiciones sobre pedidos aislados."""

    abstract = SCENARIO != 'write'
    wait_time = between(2, 4)

    def on_start(self):
        self.product_id = None
        self.order_path = None
        self.order_finished = False
        self.marker = f'LOADTEST-{uuid.uuid4().hex[:12]}'
        self.login(SELLER_EMAIL)
        dashboard = self.client.get('/vendedor/', name='GET /vendedor/ [preparación write]')
        store_match = SELLER_STORE_RE.search(dashboard.text)
        if not store_match:
            return
        self.store_id = int(store_match.group(1))
        self._create_product()
        orders = self.client.get('/gestion/pedidos/', params={'codigo_pedido': 'LOAD-WRITE'},
                                 name='GET /gestion/pedidos/ [preparación write]')
        candidates = list(dict.fromkeys(ORDER_RE.findall(orders.text)))
        if candidates:
            code, store_id = candidates[next(WRITE_USER_SEQUENCE) % len(candidates)]
            self.order_path = f'/gestion/pedidos/{code}/?tienda={store_id}'

    def _find_product_id(self, html: str):
        pattern = re.compile(
            rf'href=["\']/vendedor/tiendas/{self.store_id}/productos/(\d+)/editar/["\'][^>]*>'
            rf'(?:(?!</a>).)*?{re.escape(self.marker)}', re.DOTALL,
        )
        match = pattern.search(html)
        return int(match.group(1)) if match else None

    def _create_product(self):
        path = f'/vendedor/tiendas/{self.store_id}/productos/nuevo/'
        form = self.client.get(path, name='GET formulario crear producto')
        with self.client.post(
            path,
            data={
                'csrfmiddlewaretoken': self.csrf(form), 'nombre': self.marker,
                'descripcion': 'Producto temporal de la prueba de carga.', 'precio': '19.90',
                'marca': 'LOADTEST', 'categoria': 'tecnologia_electronica', 'disponible': 'on',
            },
            files={'imagen': ('load-test.png', PNG_BYTES, 'image/png')},
            headers={'Referer': f'{self.host}{path}'}, name='POST crear producto',
            catch_response=True,
        ) as response:
            self.product_id = self._find_product_id(response.text) if response.status_code == 200 else None
            if not self.product_id:
                response.failure('no se pudo identificar el producto temporal creado')

    @task(5)
    def edit_product(self):
        if not self.product_id:
            return
        path = f'/vendedor/tiendas/{self.store_id}/productos/{self.product_id}/editar/'
        form = self.client.get(path, name='GET formulario editar producto')
        with self.client.post(
            path,
            data={
                'csrfmiddlewaretoken': self.csrf(form), 'nombre': self.marker,
                'descripcion': 'Producto temporal editado por la prueba de carga.',
                'precio': random.choice(['18.90', '19.90', '20.90']),
                'marca': 'LOADTEST', 'categoria': 'tecnologia_electronica', 'disponible': 'on',
            },
            headers={'Referer': f'{self.host}{path}'}, name='POST editar producto',
            catch_response=True,
        ) as response:
            if response.status_code != 200 or self.marker not in response.text:
                response.failure('la edición del producto no se guardó')

    @task(1)
    def advance_order(self):
        if not self.order_path or self.order_finished:
            return
        form = self.client.get(self.order_path, name='GET formulario editar pedido')
        state_match = ORDER_STATE_RE.search(form.text)
        if not state_match:
            self.order_finished = True
            return
        with self.client.post(
            self.order_path,
            {'csrfmiddlewaretoken': self.csrf(form), 'estado': state_match.group(1)},
            headers={'Referer': f'{self.host}{self.order_path}'},
            name='POST editar estado pedido', catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f'el pedido devolvió {response.status_code}')
            if state_match.group(1) == 'recogido':
                self.order_finished = True

    def on_stop(self):
        if not self.product_id:
            return
        path = f'/vendedor/tiendas/{self.store_id}/productos/{self.product_id}/eliminar/'
        with self.client.post(
            path, {'csrfmiddlewaretoken': self.csrf()},
            headers={'Referer': f'{self.host}/vendedor/tiendas/{self.store_id}/'},
            name='POST limpiar producto temporal', catch_response=True,
        ) as response:
            if response.status_code != 200 or self.marker in response.text:
                response.failure('no se pudo limpiar el producto temporal')


@dataclass(frozen=True)
class Stage:
    duration: int
    users: int
    spawn_rate: float


PRESETS = {
    'baseline': [Stage(60, 10, 2), Stage(180, 25, 3), Stage(240, 10, 5)],
    'stress': [Stage(60, 25, 5), Stage(180, 75, 10), Stage(300, 150, 15), Stage(360, 25, 25)],
    'write': [Stage(30, 2, 1), Stage(120, 5, 1), Stage(180, 2, 2)],
}


class StagedLoadShape(LoadTestShape):
    """Rampa idéntica para los tres escenarios comparables."""
    stages = PRESETS[SCENARIO]

    def tick(self):
        elapsed = self.get_run_time()
        for stage in self.stages:
            if elapsed < stage.duration:
                return stage.users, stage.spawn_rate
        return None


@events.quitting.add_listener
def enforce_quality_gates(environment, **_kwargs):
    stats = environment.stats.total
    violations = []
    if stats.num_requests == 0:
        violations.append('no se registraron peticiones')
    if stats.fail_ratio > MAX_FAILURE_RATIO:
        violations.append(f'errores {stats.fail_ratio:.2%} > {MAX_FAILURE_RATIO:.2%}')
    p95 = stats.get_response_time_percentile(0.95) or 0
    if p95 > MAX_P95_MS:
        violations.append(f'p95 {p95:.0f} ms > {MAX_P95_MS} ms')
    if violations:
        environment.process_exit_code = 1
        print('LOAD TEST FAILED: ' + '; '.join(violations))
