from django.db import models
from django.conf import settings


class Tienda(models.Model):
    nombre = models.CharField(max_length=255)
    descripcion = models.TextField(blank=True, null=True)
    ubicacion = models.CharField(max_length=255, blank=True, null=True)
    direccion = models.CharField(max_length=255, blank=True, null=True)
    horario = models.CharField(max_length=255, blank=True, null=True)
    imagen = models.ImageField(upload_to='tiendas/', blank=True, null=True)
    vendedor = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='tienda')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.nombre

    class Meta:
        ordering = ['-created_at']

