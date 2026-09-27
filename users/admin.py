from django.contrib import admin

from .forms import AdminUserForm
from .models import User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    form = AdminUserForm
    model = User
    list_display = ('email', 'nombre', 'apellidos', 'rol', 'is_staff', 'is_active')
    list_filter = ('rol', 'is_staff', 'is_active')
    search_fields = ('email', 'nombre', 'apellidos')
    ordering = ('email',)
    readonly_fields = ('created_at', 'updated_at', 'last_login')
