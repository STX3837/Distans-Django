from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from functools import wraps
from decimal import Decimal, InvalidOperation

from users.models import User
from carts.models import Carrito, ProductoCarrito

from .forms import ProductoForm
from .models import Producto
from stores.models import Tienda


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
	productos = Producto.objects.filter(disponible=True).order_by('-destacado', 'nombre').select_related('tienda')
	return render(request, 'products/catalog.html', {'products': productos})


@buyer_or_guest_required
def store_products(request, pk):
	"""Listado de productos de una tienda concreta para compradores e invitados."""
	tienda = get_object_or_404(Tienda, pk=pk)
	productos = tienda.productos.filter(disponible=True).order_by('-destacado', 'nombre')
	return render(
		request,
		'products/store_products.html',
		{
			'store': tienda,
			'products': productos,
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
	producto = get_object_or_404(Producto, pk=pk, disponible=True)
	
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
	producto = get_object_or_404(Producto, pk=product_pk, disponible=True)
	cantidad = int(request.POST.get('cantidad', 1))
	
	if cantidad < 1:
		cantidad = 1
	
	if request.user.is_authenticated:
		# Carrito de usuario registrado
		carrito, created = Carrito.objects.get_or_create(usuario=request.user)
		item, created = ProductoCarrito.objects.get_or_create(
			carrito=carrito,
			producto=producto,
			defaults={'cantidad': cantidad}
		)
		if not created:
			item.cantidad += cantidad
			item.save()
		messages.success(request, f'{producto.nombre} añadido al carrito.')
	else:
		# Carrito de sesión para usuarios no registrados
		if 'cart' not in request.session:
			request.session['cart'] = {}
		
		cart = request.session['cart']
		product_id = str(producto.pk)
		
		if product_id in cart:
			cart[product_id]['cantidad'] += cantidad
		else:
			cart[product_id] = {
				'id': producto.pk,
				'nombre': producto.nombre,
				'precio': str(producto.precio),
				'precio_oferta': str(producto.precio_oferta) if producto.precio_oferta else None,
				'en_oferta': producto.en_oferta,
				'imagen': producto.imagen.url if producto.imagen else '',
				'cantidad': cantidad,
				'tienda_id': producto.tienda.pk,
				'tienda_nombre': producto.tienda.nombre,
			}
		request.session.modified = True
		messages.success(request, f'{producto.nombre} añadido al carrito.')
	
	return redirect('cart_view')


@buyer_or_guest_required
def cart_view(request):
	"""Vista del carrito"""
	session_items = []
	has_items = False

	if request.user.is_authenticated:
		carrito, created = Carrito.objects.get_or_create(usuario=request.user)
		items = carrito.items.select_related('producto').all()
		total = carrito.total()
		has_items = items.exists()
	else:
		carrito = None
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
						'nombre': item.get('nombre', ''),
						'tienda_nombre': item.get('tienda_nombre', ''),
						'imagen': item.get('imagen', ''),
						'cantidad': qty,
						'precio': item.get('precio'),
						'precio_oferta': item.get('precio_oferta'),
						'en_oferta': item.get('en_oferta', False),
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