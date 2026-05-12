from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('rol', User.Role.ADMIN)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    class Role(models.TextChoices):
        BUYER = 'comprador', 'Comprador'
        SELLER = 'vendedor', 'Vendedor'
        ADMIN = 'admin', 'Admin'

    email = models.EmailField(unique=True)
    nombre = models.CharField(max_length=150)
    apellidos = models.CharField(max_length=150)
    telefono = models.CharField(max_length=20, blank=True)
    direccion = models.CharField(max_length=255, blank=True)
    ciudad = models.CharField(max_length=100, blank=True)
    codigo_postal = models.CharField(max_length=20, blank=True)
    rol = models.CharField(max_length=20, choices=Role.choices, default=Role.BUYER)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['nombre', 'apellidos']

    def save(self, *args, **kwargs):
        self.is_staff = self.is_superuser or self.rol == self.Role.ADMIN
        super().save(*args, **kwargs)

    def __str__(self):
        return self.get_full_name() or self.email

    def get_full_name(self):
        return f'{self.nombre} {self.apellidos}'.strip()

    def get_short_name(self):
        return self.nombre