import json
from decimal import Decimal, InvalidOperation

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Case, Count, ExpressionWrapper, F, FloatField, Value, When
from django.db.models.functions import Least
from django.contrib import messages
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from functools import wraps
from .models import Tienda, VisitaTienda
from .forms import TiendaForm
from .utils import filter_stores_by_geo, get_catalog_mode, get_geo_search_state, set_catalog_mode as save_catalog_mode
from .utils import online_store_filter
from users.models import User
from products.models import Producto


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
	tiendas = filter_stores_by_geo(_filtered_stores(request).order_by('nombre'), geo_state)
	return render(request, 'stores/store_list.html', {
		'stores': tiendas,
		'geo_search': geo_state,
		'category_choices': Producto.CATEGORIAS_CHOICES,
		'current_category': request.GET.get('categoria', ''),
		'current_popularity_min': request.GET.get('popularidad_min', ''),
		'catalog_mode': get_catalog_mode(request),
	})


def _parse_decimal(value):
	try:
		return Decimal(value) if value not in (None, '') else None
	except (InvalidOperation, TypeError, ValueError):
		return None


def _filtered_stores(request):
	tiendas = Tienda.objects.annotate(
		visitas_count=Count('visitas', distinct=True),
		compras_count=Count('productos__productopedido__pedido', distinct=True),
	).annotate(
		popularidad_media=Case(
			When(
				visitas_count__gt=0,
				then=Least(
					ExpressionWrapper(
						(Value(4.0) + F('compras_count') * Value(5.0)) /
						(F('visitas_count') + Value(1.0)),
						output_field=FloatField(),
					),
					Value(5.0),
				),
			),
			default=Value(0.0),
			output_field=FloatField(),
		)
	)
	if get_catalog_mode(request) == 'online':
		tiendas = tiendas.filter(online_store_filter())
	categoria = request.GET.get('categoria', '').strip()
	popularidad_min = _parse_decimal(request.GET.get('popularidad_min'))
	if categoria:
		tiendas = tiendas.filter(productos__categoria=categoria).distinct()
	if popularidad_min is not None:
		tiendas = tiendas.filter(popularidad_media__gte=max(Decimal('0'), min(popularidad_min, Decimal('5'))))
	return tiendas


@buyer_or_guest_required
def store_map(request):
	"""Mapa interactivo con las tiendas filtradas por ubicacion/radio para compradores e invitados."""
	geo_state = get_geo_search_state(request)
	tiendas = _filtered_stores(request).filter(latitud__isnull=False, longitud__isnull=False).order_by('nombre')
	tiendas = filter_stores_by_geo(tiendas, geo_state)
	selected_store_id = request.GET.get('tienda')

	store_data = []
	for tienda in tiendas:
		store_data.append({
			'id': tienda.pk,
			'name': tienda.nombre,
			'description': tienda.descripcion or '',
			'address': tienda.direccion or '',
			'latitude': float(tienda.latitud),
			'longitude': float(tienda.longitud),
			'products_url': reverse('store_products', args=[tienda.pk]),
			'selected': str(tienda.pk) == str(selected_store_id),
		})

	context = {
		'stores': tiendas,
		'geo_search': geo_state,
		'stores_map_data': json.dumps(store_data, ensure_ascii=False),
		'map_center_lat': geo_state['latitude'] if geo_state['latitude'] is not None else 40.4168,
		'map_center_lng': geo_state['longitude'] if geo_state['longitude'] is not None else -3.7038,
		'selected_store_id': selected_store_id or '',
	}
	return render(request, 'stores/store_map.html', context)


@require_http_methods(['POST'])
def set_catalog_mode(request):
	save_catalog_mode(request, request.POST.get('catalog_mode'))
	return redirect(request.POST.get('next') or request.META.get('HTTP_REFERER') or 'catalog')


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
