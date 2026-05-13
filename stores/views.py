from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from functools import wraps
from .models import Tienda
from .forms import TiendaForm
from users.models import User


def buyer_or_guest_required(view_func):
	"""Decorador que requiere estar autenticado como comprador o como invitado."""
	@wraps(view_func)
	def wrapper(request, *args, **kwargs):
		# Si está autenticado como comprador
		if request.user.is_authenticated and request.user.rol == User.Role.BUYER:
			return view_func(request, *args, **kwargs)
		
		# Si es invitado (tiene la marca de sesión)
		if request.session.get('guest') == True:
			return view_func(request, *args, **kwargs)
		
		# En cualquier otro caso, redirigir al login
		return redirect('login')
	return wrapper


@buyer_or_guest_required
def store_list(request):
	"""Listado público/administrativo de tiendas."""
	tiendas = Tienda.objects.all().order_by('nombre')
	return render(request, 'stores/store_list.html', {'stores': tiendas})


@login_required
def store_list_admin(request):
	"""Listado de tiendas para administración (solo admins)."""
	if not (request.user.is_staff or request.user.rol == User.Role.ADMIN):
		return redirect('catalog')

	tiendas = Tienda.objects.all().order_by('nombre')
	return render(request, 'stores/store_list_admin.html', {'stores': tiendas})


@login_required
def store_create_admin(request):
	"""Crear nueva tienda (solo admins)."""
	if not (request.user.is_staff or request.user.rol == User.Role.ADMIN):
		return redirect('catalog')

	if request.method == 'POST':
		form = TiendaForm(request.POST, request.FILES)
		if form.is_valid():
			tienda = form.save(commit=False)
			tienda.save()
			messages.success(request, 'La tienda se ha creado correctamente.')
			return redirect('store_list_admin')
	else:
		form = TiendaForm()

	return render(request, 'stores/store_form.html', {'form': form, 'title': 'Nueva tienda'})


@login_required
def store_update_admin(request, pk):
	"""Editar tienda (solo admins)."""
	if not (request.user.is_staff or request.user.rol == User.Role.ADMIN):
		return redirect('catalog')

	tienda = get_object_or_404(Tienda, pk=pk)

	if request.method == 'POST':
		form = TiendaForm(request.POST, request.FILES, instance=tienda)
		if form.is_valid():
			form.save()
			messages.success(request, 'La tienda se ha actualizado correctamente.')
			return redirect('store_list_admin')
	else:
		form = TiendaForm(instance=tienda)

	return render(request, 'stores/store_form.html', {'form': form, 'store': tienda, 'title': f'Editar {tienda.nombre}'})


@login_required
def store_delete_admin(request, pk):
	"""Eliminar tienda (solo admins)."""
	if not (request.user.is_staff or request.user.rol == User.Role.ADMIN):
		return redirect('catalog')

	tienda = get_object_or_404(Tienda, pk=pk)

	if request.method == 'POST':
		tienda.delete()
		messages.success(request, 'La tienda se ha eliminado correctamente.')
		return redirect('store_list_admin')

	return render(request, 'stores/store_confirm_delete.html', {'store': tienda})

