# Distans-Django 🌍

Proyecto base configurado con **Django**, **GeoDjango** y **PostgreSQL + PostGIS**, completamente dockerizado para facilitar su desarrollo y despliegue.

## 📋 Requisitos previos

Para ejecutar este proyecto en tu máquina local, necesitas:

- **Git**
- **Docker Desktop** (incluye Docker Compose)

## 🚀 Instalación y despliegue local

Sigue estos pasos para levantar el entorno desde cero.

### 1. Clonar el repositorio

Repositorio: [https://github.com/STX3837/Distans-Django.git](https://github.com/STX3837/Distans-Django.git)

```bash
git clone https://github.com/STX3837/Distans-Django.git
cd Distans-Django
```

### 2. Configurar variables de entorno

Crea un archivo `.env` en la raíz del proyecto (al mismo nivel que `docker-compose.yml`) con este contenido:

```env
DB_NAME=mi_base_datos
DB_USER=mi_usuario
DB_PASSWORD=una_contrasena_segura
```

### 3. Construir y levantar contenedores

Con Docker ejecutándose, inicia los servicios en segundo plano:

```bash
docker compose up -d --build
```

Nota: La primera ejecución puede tardar varios minutos porque se descargan imágenes y se construyen contenedores.

### 4. Aplicar migraciones

Prepara la base de datos creando las tablas necesarias:

```bash
docker compose exec web python manage.py migrate
```

### 5. Crear superusuario (opcional)

Para acceder al panel de administración de Django:

```bash
docker compose exec web python manage.py createsuperuser
```

## 💻 Acceso a la aplicación

Una vez completados los pasos anteriores:

- Aplicación web: http://localhost:8000
- Panel de administración: http://localhost:8000/admin

## 🛠️ Comandos útiles

Como el proyecto está encapsulado en Docker, los comandos de Django se ejecutan dentro del contenedor `web`.

Detener contenedores:

```bash
docker compose down
```

Ver logs en tiempo real:

```bash
docker compose logs -f web
```

Crear una nueva app de Django:

```bash
docker compose exec web python manage.py startapp nombre_de_la_app
```

Crear nuevas migraciones:

```bash
docker compose exec web python manage.py makemigrations
```

Abrir el shell de Django:

```bash
docker compose exec web python manage.py shell
```