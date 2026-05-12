from django.db import models
from stores.models import Tienda


class Producto(models.Model):
    CATEGORIAS_CHOICES = [
        ('cultura_ocio', 'Cultura y ocio'),
        ('hogar_bricolaje', 'Hogar y bricolaje'),
        ('salud_bienestar', 'Salud y bienestar'),
        ('tecnologia_electronica', 'Tecnología y electrónica'),
        ('floristeria_jardineria', 'Floristería y jardinería'),
        ('alimentacion_bebidas', 'Alimentación y bebidas'),
        ('moda_complementos', 'Moda y complementos'),
        ('papeleria_oficina', 'Papelería y oficina'),
    ]

    nombre = models.CharField(max_length=255)
    descripcion = models.TextField()
    precio = models.DecimalField(max_digits=10, decimal_places=2)
    precio_oferta = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        blank=True, 
        null=True,
        help_text="Precio con descuento"
    )
    en_oferta = models.BooleanField(default=False)
    marca = models.CharField(max_length=100)
    categoria = models.CharField(
        max_length=50,
        choices=CATEGORIAS_CHOICES
    )
    imagen = models.ImageField(upload_to='productos/')
    disponible = models.BooleanField(default=True)
    destacado = models.BooleanField(default=False)
    stock = models.IntegerField(default=0)
    tienda = models.ForeignKey(Tienda, on_delete=models.CASCADE, related_name='productos', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.nombre

    def porcentaje_descuento(self):
        """Calcula el porcentaje de descuento si hay oferta"""
        if self.precio_oferta and self.precio > 0:
            descuento = ((self.precio - self.precio_oferta) / self.precio) * 100
            return round(descuento, 2)
        return None

    def tiene_oferta(self):
        """Verifica si el producto está marcado en oferta y el precio de oferta es válido"""
        return bool(self.en_oferta and self.precio_oferta is not None and self.precio_oferta < self.precio)

    class Meta:
        ordering = ['-created_at']
