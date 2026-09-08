from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import AccountUpdateForm, AdminUserForm, SignUpForm
from .models import Favorite, User
from products.models import Producto
from stores.models import Tienda


def is_staff_user(user):
    return user.is_staff


def can_delete_user(request_user, target_user):
    return request_user.pk != target_user.pk and not target_user.is_superuser


def signup(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Cuenta creada correctamente. Por favor, inicia sesión.')
            return redirect('login')
    else:
        form = SignUpForm()

    return render(request, 'users/signup.html', {'form': form})


@login_required
def post_login_redirect(request):
    # Al iniciar sesión normal, se elimina el estado de invitado.
    request.session.pop('guest', None)

    # Comprador -> catálogo de productos
    if request.user.rol == User.Role.BUYER:
        return redirect('catalog')

    # Vendedor -> panel de vendedor
    if request.user.rol == User.Role.SELLER:
        try:
            return redirect('seller_home')
        except Exception:
            return redirect('account_detail')

    # Admin / staff -> panel de administración de tiendas
    if request.user.is_staff or request.user.rol == User.Role.ADMIN:
        return redirect('store_list_admin')

    return redirect('account_detail')


def guest_login(request):
    """Iniciar sesión como invitado (sin crear usuario). Guarda una marca en sesión."""
    # Clear any existing authenticated session
    try:
        from django.contrib.auth import logout
        logout(request)
    except Exception:
        pass

    request.session['guest'] = True
    return redirect('catalog')


def logout_and_clear(request):
    """Logout and clear guest flag from session."""
    try:
        from django.contrib.auth import logout
        logout(request)
    except Exception:
        pass

    request.session.pop('guest', None)
    return redirect('login')


@login_required
def account_detail(request):
    if request.method == 'POST':
        form = AccountUpdateForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Los datos de la cuenta se han actualizado correctamente.')
            return redirect('account_detail')
    else:
        form = AccountUpdateForm(instance=request.user)

    return render(request, 'users/account_detail.html', {'form': form})


def _buyer_only(request):
    return request.user.is_authenticated and request.user.rol == User.Role.BUYER


def _favorite_redirect(request, fallback):
    next_url = request.POST.get('next', '')
    if next_url.startswith('/') and not next_url.startswith('//'):
        return redirect(next_url)
    return redirect(fallback)


@login_required
def favorites(request):
    if not _buyer_only(request):
        return redirect('account_detail')

    favorite_items = Favorite.objects.filter(usuario=request.user).select_related('producto', 'tienda')
    return render(
        request,
        'users/favorites.html',
        {
            'favorite_items': favorite_items,
            'favorite_products': favorite_items.filter(producto__isnull=False),
            'favorite_stores': favorite_items.filter(tienda__isnull=False),
        },
    )


@login_required
@require_POST
def toggle_product_favorite(request, pk):
    if not _buyer_only(request):
        return redirect('account_detail')

    producto = get_object_or_404(Producto, pk=pk)
    favorite, created = Favorite.objects.get_or_create(usuario=request.user, producto=producto)
    if not created:
        favorite.delete()
        messages.info(request, f'{producto.nombre} eliminado de favoritos.')
    else:
        messages.success(request, f'{producto.nombre} añadido a favoritos.')
    return _favorite_redirect(request, f'/productos/{producto.pk}/')


@login_required
@require_POST
def toggle_store_favorite(request, pk):
    if not _buyer_only(request):
        return redirect('account_detail')

    tienda = get_object_or_404(Tienda, pk=pk)
    favorite, created = Favorite.objects.get_or_create(usuario=request.user, tienda=tienda)
    if not created:
        favorite.delete()
        messages.info(request, f'{tienda.nombre} eliminada de favoritos.')
    else:
        messages.success(request, f'{tienda.nombre} añadida a favoritos.')
    return _favorite_redirect(request, '/tiendas/')


@user_passes_test(is_staff_user)
def admin_user_list(request):
    users = User.objects.order_by('email')
    return render(request, 'users/admin_user_list.html', {'users': users})


@user_passes_test(is_staff_user)
def admin_user_create(request):
    if request.method == 'POST':
        form = AdminUserForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'El usuario se ha creado correctamente.')
            return redirect('admin_user_list')
    else:
        form = AdminUserForm()

    return render(request, 'users/admin_user_form.html', {'form': form, 'title': 'Crear usuario'})


@user_passes_test(is_staff_user)
def admin_user_update(request, pk):
    user_obj = get_object_or_404(User, pk=pk)

    if request.method == 'POST':
        form = AdminUserForm(request.POST, instance=user_obj)
        if form.is_valid():
            form.save()
            messages.success(request, 'El usuario se ha actualizado correctamente.')
            return redirect('admin_user_list')
    else:
        form = AdminUserForm(instance=user_obj)

    return render(request, 'users/admin_user_form.html', {'form': form, 'title': 'Editar usuario'})


@user_passes_test(is_staff_user)
def admin_user_delete(request, pk):
    user_obj = get_object_or_404(User, pk=pk)
    can_delete = can_delete_user(request.user, user_obj)

    if request.method == 'POST':
        if not can_delete:
            if request.user.pk == user_obj.pk:
                messages.error(request, 'No puedes eliminar tu propia cuenta.')
            else:
                messages.error(request, 'No se puede eliminar a un superusuario.')
            return redirect('admin_user_list')

        user_obj.delete()
        messages.success(request, 'El usuario se ha eliminado correctamente.')
        return redirect('admin_user_list')

    return render(
        request,
        'users/admin_user_confirm_delete.html',
        {
            'user_obj': user_obj,
            'can_delete': can_delete,
        },
    )