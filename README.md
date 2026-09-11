# Distans-Django

Aplicacion web para conectar comercios y compradores mediante Django, GeoDjango y PostgreSQL con PostGIS. El proyecto esta preparado para ejecutarse con Docker Compose, que proporciona Django, GDAL, PostgreSQL y PostGIS en un entorno reproducible.

## Requisitos

- Git
- Docker Desktop con Docker Compose

No es necesario instalar Python, Django, GDAL ni PostgreSQL en Windows si se utiliza Docker.

## Instalacion

### 1. Clonar el repositorio

```bash
git clone https://github.com/STX3837/Distans-Django.git
cd Distans-Django
```

### 2. Crear el archivo `.env`

Crea `.env` en la raiz del proyecto, junto a `docker-compose.yml`:

```env
DB_NAME=mi_base_datos
DB_USER=mi_usuario
DB_PASSWORD=una_contrasena_segura

# Opcional. Necesario para probar los pagos con Stripe.
STRIPE_PUBLIC_KEY=pk_test_REPLACE_WITH_YOUR_KEY
STRIPE_SECRET_KEY=sk_test_REPLACE_WITH_YOUR_KEY
STRIPE_WEBHOOK_SECRET=whsec_REPLACE_WITH_YOUR_SECRET

# Opcionales para el entorno local.
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
```

El archivo `.env` no debe subirse al repositorio. Para una prueba sin Stripe se pueden dejar vacias sus tres variables; el pago contra reembolso seguira disponible.

### 3. Construir y arrancar los servicios

Con Docker Desktop en ejecucion:

```bash
docker compose up -d --build
```

La primera ejecucion puede tardar varios minutos. Los servicios principales son:

- `web`: aplicacion Django en `http://localhost:8000`.
- `db`: PostgreSQL con PostGIS.
- `cart_cleanup`: limpieza automatica de carritos de invitados caducados.

### 4. Aplicar migraciones

```bash
docker compose exec web python manage.py migrate
```

Si la base de datos aun esta arrancando, espera unos segundos y repite el comando.

### 5. Crear un usuario administrador

```bash
docker compose exec web python manage.py createsuperuser
```

El panel de administracion esta disponible en `http://localhost:8000/admin`.

## Probar Stripe

Stripe debe utilizarse en modo test. Al iniciar el pago mediante pasarela, utiliza estos datos:

| Campo | Valor |
| --- | --- |
| Numero de tarjeta | `4242 4242 4242 4242` |
| Caducidad | Cualquier fecha futura, por ejemplo `12/34` |
| CVC | Cualquier numero de tres digitos, por ejemplo `123` |
| Codigo postal | Cualquier codigo postal valido |

No utilices tarjetas reales. Las claves `pk_test_`, `sk_test_` y `whsec_` deben pertenecer a una cuenta de Stripe en modo test.

## Ejecutar las pruebas

La suite completa se ejecuta dentro del contenedor para disponer de PostGIS y GDAL:

```bash
docker compose run --rm web python manage.py test
```

Comprobar que no faltan migraciones:

```bash
docker compose run --rm web python manage.py makemigrations --check --dry-run
```

## Comandos utiles

Ver los logs de Django:

```bash
docker compose logs -f web
```

Abrir un shell de Django:

```bash
docker compose exec web python manage.py shell
```

Crear nuevas migraciones:

```bash
docker compose exec web python manage.py makemigrations
```

Limpiar carritos de invitados manualmente:

```bash
docker compose exec web python manage.py cleanup_guest_carts
```

Simular la limpieza sin borrar datos:

```bash
docker compose exec web python manage.py cleanup_guest_carts --dry-run
```

Ver los logs del limpiador automatico:

```bash
docker compose logs -f cart_cleanup
```

El limpiador se ejecuta cada 24 horas por defecto. El intervalo se puede cambiar con `CART_CLEANUP_INTERVAL_SECONDS` en `docker-compose.yml`.

## Detener el proyecto

```bash
docker compose down
```

Para detener los contenedores y eliminar tambien el volumen de PostgreSQL:

```bash
docker compose down -v
```

El segundo comando borra los datos almacenados en la base de datos.