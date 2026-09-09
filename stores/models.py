from django.db import models
from django.conf import settings


class Tienda(models.Model):
    class Plan(models.TextChoices):
        FREEMIUM = 'freemium', 'Freemium'
        PREMIUM = 'premium', 'Premium'

    nombre = models.CharField(max_length=255)
    descripcion = models.TextField(blank=True, null=True)
    ubicacion = models.CharField(max_length=255, blank=True, null=True)
    direccion = models.CharField(max_length=255, blank=True, null=True)
    latitud = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)
    longitud = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)
    horario = models.CharField(max_length=255, blank=True, null=True)
    informacion_apertura = models.TextField(blank=True, null=True)
    plan = models.CharField(max_length=10, choices=Plan.choices, default=Plan.PREMIUM)
    suscripcion_activa = models.BooleanField(default=True)
    pasarela_activa = models.BooleanField(default=True)
    fecha_alta = models.DateField(auto_now_add=True)
    fecha_renovacion = models.DateField(blank=True, null=True)
    imagen = models.ImageField(upload_to='tiendas/', blank=True, null=True)
    vendedor = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='tienda')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.nombre

    @property
    def permite_compra_online(self):
        return self.plan == self.Plan.PREMIUM and self.suscripcion_activa and self.pasarela_activa

    class Meta:
        ordering = ['-created_at']


class VisitaTienda(models.Model):
    tienda = models.ForeignKey(Tienda, on_delete=models.CASCADE, related_name='visitas')
    session_key = models.CharField(max_length=40, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=['tienda', 'created_at'], name='stores_vis_tienda_6b7e8e_idx')]

