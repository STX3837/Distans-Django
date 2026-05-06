# Usar una imagen oficial de Python ligera
FROM python:3.11-slim

# Evitar que Python escriba archivos .pyc y forzar la salida estándar (logs)
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Instalar dependencias del sistema operativo requeridas por GeoDjango
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        binutils \
        libproj-dev \
        gdal-bin \
        python3-gdal \
        libpq-dev \
        gcc \
    && rm -rf /var/lib/apt/lists/*

# Crear y establecer el directorio de trabajo dentro del contenedor
WORKDIR /app

# Copiar el archivo de requerimientos e instalarlos
COPY requirements.txt /app/
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copiar el resto del código del proyecto
COPY . /app/