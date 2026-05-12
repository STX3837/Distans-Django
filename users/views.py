from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import get_object_or_404, redirect, render

from .forms import AccountUpdateForm, AdminUserForm, SignUpForm
from .models import User


def is_staff_user(user):
    return user.is_staff


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

    if request.method == 'POST':
        user_obj.delete()
        messages.success(request, 'El usuario se ha eliminado correctamente.')
        return redirect('admin_user_list')

    return render(request, 'users/admin_user_confirm_delete.html', {'user_obj': user_obj})