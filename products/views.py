from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.forms import modelformset_factory
from django.shortcuts import get_object_or_404, redirect, render
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from functools import wraps
from decimal import Decimal, InvalidOperation

from users.models import User
from carts.models import Carrito, ProductoCarrito

from .forms import ProductoForm, ProductoStockForm
from .models import Producto
from stores.models import Tienda
from stores.utils import filter_products_by_geo, get_geo_search_state, store_is_within_radius


def _ensure_session_key(request):
	if not request.session.session_key:
		request.session.create()
	return request.session.session_key


def _get_or_create_cart(request):
	if request.user.is_authenticated:
		cart, _ = Carrito.objects.get_or_create(
			usuario=request.user,
			defaults={'sesion': _ensure_session_key(request)},
		)
		return cart

	session_key = _ensure_session_key(request)
	cart, _ = Carrito.objects.get_or_create(usuario=None, sesion=session_key)
	return cart


def _has_quantity_plan(producto):
	"""Mientras no exista un campo formal de plan, se permite gestionar cantidades por defecto."""
	vendedor = getattr(getattr(producto, 'tienda', None), 'vendedor', None)
	plan = getattr(vendedor, 'plan', None)
	if plan is None:
		return True
	return str(plan).lower() in {'premium', 'pro', 'plus', 'business'}


def _is_product_orderable(producto):
	return bool(producto.disponible and producto.stock > 0)


def _to_int(value, default=1):
	try:
		return int(value)
	except (TypeError, ValueError):
		return default


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
def catalog(request):
	"""Listado público de productos de todas las tiendas."""
	geo_state = get_geo_search_state(request)
	productos = Producto.objects.select_related('tienda')
	productos = filter_products_by_geo(productos, geo_state).order_by('-disponible', '-destacado', 'nombre')
	return render(request, 'products/catalog.html', {'products': productos, 'geo_search': geo_state})


@buyer_or_guest_required
def store_products(request, pk):
	"""Listado de productos de una tienda concreta para compradores e invitados."""
	tienda = get_object_or_404(Tienda, pk=pk)
	geo_state = get_geo_search_state(request)
	store_allowed = store_is_within_radius(tienda, geo_state['latitude'], geo_state['longitude'], geo_state['radius_km'])
	productos = tienda.productos.filter(disponible=True).order_by('-destacado', 'nombre') if store_allowed else tienda.productos.none()
	return render(
		request,
		'products/store_products.html',
		{
			'store': tienda,
			'products': productos,
			'geo_search': geo_state,
			'store_in_radius': store_allowed,
		},
	)


def _is_seller(user):
	return user.is_authenticated and (user.rol == User.Role.SELLER or user.is_staff or user.rol == User.Role.ADMIN)


def _get_accessible_stores(user):
	if user.is_staff or user.rol == User.Role.ADMIN:
		return Tienda.objects.select_related('vendedor').all().order_by('nombre')

	tienda = getattr(user, 'tienda', None)
	if tienda is None:
		return Tienda.objects.none()

	return Tienda.objects.filter(pk=tienda.pk).select_related('vendedor')


def _get_store_for_user(user, store_pk):
	if user.is_staff or user.rol == User.Role.ADMIN:
		return get_object_or_404(Tienda, pk=store_pk)

	return get_object_or_404(Tienda, pk=store_pk, vendedor=user)


def _get_product_for_store(user, store_pk, pk):
	tienda = _get_store_for_user(user, store_pk)
	return tienda, get_object_or_404(Producto, pk=pk, tienda=tienda)


@login_required
def seller_home(request):
	if not _is_seller(request.user):
		return redirect('account_detail')

	stores = _get_accessible_stores(request.user)
	return render(request, 'products/seller_home.html', {'stores': stores})


@login_required
def store_detail(request, pk):
	if not _is_seller(request.user):
		return redirect('account_detail')

	tienda = _get_store_for_user(request.user, pk)
	productos = tienda.productos.order_by('nombre')

	return render(
		request,
		'products/store_detail.html',
		{
			'store': tienda,
			'products': productos,
		},
	)


@login_required
def store_stock_edit(request, pk):
	if not _is_seller(request.user):
		return redirect('account_detail')

	tienda = _get_store_for_user(request.user, pk)
	productos_qs = tienda.productos.order_by('nombre')
	StockFormSet = modelformset_factory(Producto, form=ProductoStockForm, extra=0)

	if request.method == 'POST':
		formset = StockFormSet(request.POST, queryset=productos_qs)
		if formset.is_valid():
			formset.save()
			messages.success(request, 'El stock se ha actualizado correctamente.')
			return redirect('store_detail', pk=tienda.pk)
	else:
		formset = StockFormSet(queryset=productos_qs)

	return render(
		request,
		'products/store_stock_edit.html',
		{
			'store': tienda,
			'formset': formset,
			'products': productos_qs,
		},
	)


@login_required
def product_create(request, store_pk):
	if not _is_seller(request.user):
		return redirect('account_detail')

	tienda = _get_store_for_user(request.user, store_pk)

	if request.method == 'POST':
		form = ProductoForm(request.POST, request.FILES)
		if form.is_valid():
			producto = form.save(commit=False)
			producto.tienda = tienda
			producto.save()
			messages.success(request, 'El producto se ha creado correctamente.')
			return redirect('store_detail', pk=tienda.pk)
	else:
		form = ProductoForm()

	return render(
		request,
		'products/product_form.html',
		{
			'form': form,
			'store': tienda,
			'title': 'Nuevo producto',
			'submit_label': 'Guardar',
		},
	)


@login_required
def product_update(request, store_pk, pk):
	if not _is_seller(request.user):
		return redirect('account_detail')

	tienda, producto = _get_product_for_store(request.user, store_pk, pk)

	if request.method == 'POST':
		form = ProductoForm(request.POST, request.FILES, instance=producto)
		if form.is_valid():
			form.save()
			messages.success(request, 'El producto se ha actualizado correctamente.')
			return redirect('store_detail', pk=tienda.pk)
	else:
		form = ProductoForm(instance=producto)

	return render(
		request,
		'products/product_form.html',
		{
			'form': form,
			'store': tienda,
			'product': producto,
			'title': producto.nombre,
			'submit_label': 'Guardar cambios',
		},
	)


@login_required
def product_delete(request, store_pk, pk):
	if not _is_seller(request.user):
		return redirect('account_detail')

	tienda, producto = _get_product_for_store(request.user, store_pk, pk)

	if request.method == 'POST':
		producto.delete()
		messages.success(request, 'El producto se ha eliminado correctamente.')
		return redirect('store_detail', pk=tienda.pk)

	return render(
		request,
		'products/product_confirm_delete.html',
		{
			'store': tienda,
			'product': producto,
		},
	)


# Vistas públicas para compradores
@buyer_or_guest_required
def product_detail(request, pk):
	"""Detalle del producto - accesible para registrados y no registrados"""
	producto = get_object_or_404(Producto, pk=pk)
	
	return render(
		request,
		'products/product_detail.html',
		{
			'product': producto,
		},
	)


@require_http_methods(["POST"])
@buyer_or_guest_required
def add_to_cart(request, product_pk):
	"""Agregar producto al carrito"""
	producto = get_object_or_404(Producto, pk=product_pk)
	cantidad = _to_int(request.POST.get('cantidad', 1), default=1)
	
	if cantidad < 1:
		cantidad = 1

	if not _is_product_orderable(producto):
		messages.error(request, 'Este producto no está disponible para compra en este momento.')
		return redirect('product_detail', pk=producto.pk)
	
	if request.user.is_authenticated:
		# Carrito de usuario registrado
		carrito = _get_or_create_cart(request)
		item, created = ProductoCarrito.objects.get_or_create(
			carrito=carrito,
			producto=producto,
			defaults={'cantidad': cantidad}
		)
		if not created:
			item.cantidad = min(item.cantidad + cantidad, producto.stock)
			item.save()
		messages.success(request, f'{producto.nombre} añadido al carrito.')
	else:
		# Carrito de sesión para usuarios no registrados
		_ensure_session_key(request)
		_get_or_create_cart(request)
		if 'cart' not in request.session:
			request.session['cart'] = {}
		
		cart = request.session['cart']
		product_id = str(producto.pk)
		
		if product_id in cart:
			cart[product_id]['cantidad'] = min(cart[product_id]['cantidad'] + cantidad, producto.stock)
		else:
			cart[product_id] = {
				'id': producto.pk,
				'nombre': producto.nombre,
				'precio': str(producto.precio),
				'precio_oferta': str(producto.precio_oferta) if producto.precio_oferta else None,
				'en_oferta': producto.en_oferta,
				'porcentaje_descuento': str(producto.porcentaje_descuento()) if producto.tiene_oferta() else None,
				'imagen': producto.imagen.url if producto.imagen else '',
				'cantidad': cantidad,
				'tienda_id': producto.tienda.pk,
				'tienda_nombre': producto.tienda.nombre,
			}
		request.session.modified = True
		messages.success(request, f'{producto.nombre} añadido al carrito.')
	
	return redirect('cart_view')


@require_http_methods(["POST"])
@buyer_or_guest_required
def update_cart_item(request, product_pk):
	"""Actualizar cantidad de un producto del carrito."""
	producto = get_object_or_404(Producto, pk=product_pk)
	nueva_cantidad = _to_int(request.POST.get('cantidad', 1), default=1)

	if not _has_quantity_plan(producto):
		messages.warning(request, 'El plan del vendedor no permite gestionar cantidades para este producto.')
		return redirect('cart_view')

	if nueva_cantidad <= 0:
		return remove_cart_item(request, product_pk)

	nueva_cantidad = min(nueva_cantidad, max(producto.stock, 1))

	if request.user.is_authenticated:
		carrito = _get_or_create_cart(request)
		item = carrito.items.filter(producto=producto).first()
		if item:
			item.cantidad = nueva_cantidad
			item.save(update_fields=['cantidad', 'updated_at'])
	else:
		cart = request.session.get('cart', {})
		product_id = str(producto.pk)
		if product_id in cart:
			cart[product_id]['cantidad'] = nueva_cantidad
			request.session['cart'] = cart
			request.session.modified = True

	messages.success(request, 'Cantidad actualizada.')
	return redirect('cart_view')


@require_http_methods(["POST"])
@buyer_or_guest_required
def remove_cart_item(request, product_pk):
	"""Eliminar un producto del carrito."""
	producto = get_object_or_404(Producto, pk=product_pk)

	if request.user.is_authenticated:
		carrito = _get_or_create_cart(request)
		carrito.items.filter(producto=producto).delete()
	else:
		cart = request.session.get('cart', {})
		product_id = str(producto.pk)
		if product_id in cart:
			del cart[product_id]
			request.session['cart'] = cart
			request.session.modified = True

	messages.success(request, 'Producto eliminado del carrito.')
	return redirect('cart_view')


@buyer_or_guest_required
def cart_view(request):
	"""Vista del carrito"""
	session_items = []
	has_items = False

	if request.user.is_authenticated:
		carrito = _get_or_create_cart(request)
		items = carrito.items.select_related('producto').all()
		total = carrito.total()
		has_items = items.exists()
	else:
		carrito = _get_or_create_cart(request)
		items = []
		total = Decimal('0.00')
		
		if 'cart' in request.session:
			cart_data = request.session['cart']
			for item in cart_data.values():
				try:
					unit_price = Decimal(item.get('precio_oferta') or item.get('precio') or '0')
				except (InvalidOperation, TypeError):
					unit_price = Decimal('0')

				qty = int(item.get('cantidad', 0))
				subtotal = unit_price * qty
				total += subtotal

				session_items.append(
					{
						'id': item.get('id'),
						'nombre': item.get('nombre', ''),
						'tienda_nombre': item.get('tienda_nombre', ''),
						'imagen': item.get('imagen', ''),
						'cantidad': qty,
						'precio': item.get('precio'),
						'precio_oferta': item.get('precio_oferta'),
						'en_oferta': item.get('en_oferta', False),
						'porcentaje_descuento': item.get('porcentaje_descuento'),
						'subtotal': subtotal,
					}
				)

			has_items = len(session_items) > 0
	
	return render(
		request,
		'carts/cart_view.html',
		{
			'carrito': carrito,
			'items': items,
			'session_items': session_items,
			'has_items': has_items,
			'total': total,
		},
	)

@login_required
def store_update(request, pk):
	"""Editar información de la tienda (vendedor o admin)"""
	if not _is_seller(request.user):
		return redirect('account_detail')

	tienda = _get_store_for_user(request.user, pk)

	if request.method == 'POST':
		from stores.forms import TiendaForm
		form = TiendaForm(request.POST, request.FILES, instance=tienda)
		if form.is_valid():
			form.save()
			messages.success(request, 'La tienda se ha actualizado correctamente.')
			return redirect('store_detail', pk=tienda.pk)
	else:
		from stores.forms import TiendaForm
		form = TiendaForm(instance=tienda)

	return render(
		request,
		'stores/store_form.html',
		{
			'store': tienda,
			'form': form,
			'title': f'Editar {tienda.nombre}',
		},
	)