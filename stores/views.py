from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from functools import wraps
from .models import Tienda
from .forms import TiendaForm
from .utils import filter_stores_by_geo, get_geo_search_state
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
	geo_state = get_geo_search_state(request)
	tiendas = filter_stores_by_geo(Tienda.objects.all().order_by('nombre'), geo_state)
	return render(request, 'stores/store_list.html', {'stores': tiendas, 'geo_search': geo_state})


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
			if tienda.ubicacion is None:
				tienda.ubicacion = ''
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


@require_http_methods(["POST"])
def set_search_location(request):
	latitude = request.POST.get('latitude')
	longitude = request.POST.get('longitude')
	next_url = request.POST.get('next') or request.META.get('HTTP_REFERER') or '/'

	try:
		latitude_value = float(latitude)
		longitude_value = float(longitude)
	except (TypeError, ValueError):
		messages.error(request, 'Selecciona una ubicación válida en el mapa.')
		return redirect(next_url)

	request.session['search_latitude'] = latitude_value
	request.session['search_longitude'] = longitude_value
	request.session.modified = True
	messages.success(request, 'Ubicación guardada para la búsqueda.')
	return redirect(next_url)


@require_http_methods(["POST"])
def set_search_radius(request):
	radius_value = request.POST.get('radius_value')
	radius_mode = request.POST.get('radius_mode', 'preset')
	next_url = request.POST.get('next') or request.META.get('HTTP_REFERER') or '/'

	if radius_mode == 'none' or radius_value in (None, '', 'none'):
		request.session.pop('search_radius_km', None)
		request.session.modified = True
		messages.success(request, 'Se mostrará todo sin aplicar radio.')
		return redirect(next_url)

	try:
		radius_km = float(radius_value)
		if radius_km <= 0:
			raise ValueError
	except (TypeError, ValueError):
		messages.error(request, 'Selecciona un radio válido.')
		return redirect(next_url)

	request.session['search_radius_km'] = radius_km
	request.session.modified = True
	messages.success(request, f'Radio de {radius_km:g} km guardado.')
	return redirect(next_url)


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

