from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import get_object_or_404, redirect, render

from .forms import AccountUpdateForm, AdminUserForm, SignUpForm
from .models import User


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
    if request.user.rol == User.Role.SELLER:
        try:
            return redirect('seller_home')
        except Exception:
            return redirect('account_detail')

    if request.user.is_staff or request.user.rol == User.Role.ADMIN:
        return redirect('admin_user_list')

    return redirect('account_detail')


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