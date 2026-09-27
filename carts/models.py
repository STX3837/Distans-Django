from django.db import models
from django.conf import settings
from django.db.models import Q
from products.models import Producto


class Carrito(models.Model):
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='carrito',
        blank=True,
        null=True,
    )
    sesion = models.CharField(max_length=255, blank=True, null=True, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        if self.usuario_id:
            return f"Carrito de {self.usuario.email}"
        return f"Carrito invitado {self.sesion or 'sin-sesion'}"

    def total(self):
        """Calcula el total del carrito"""
        return sum(item.subtotal() for item in self.items.all())

    class Meta:
        ordering = ['-updated_at']
        constraints = [
            models.CheckConstraint(
                check=Q(usuario__isnull=False) | Q(sesion__isnull=False),
                name='cart_owner_user_or_session',
            ),
        ]


class ProductoCarrito(models.Model):
    carrito = models.ForeignKey(Carrito, on_delete=models.CASCADE, related_name='items')
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    cantidad = models.IntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.cantidad}x {self.producto.nombre}"

    def subtotal(self):
        """Calcula el subtotal de este item en el carrito"""
        precio = self.producto.precio_oferta if self.producto.tiene_oferta() else self.producto.precio
        return precio * self.cantidad

    class Meta:
        unique_together = ('carrito', 'producto')

