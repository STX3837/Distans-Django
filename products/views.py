from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from users.models import User

from .forms import ProductoForm
from .models import Producto
from stores.models import Tienda


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
