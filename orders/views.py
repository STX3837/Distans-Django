from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from products.views import buyer_or_guest_required, _is_seller
from stores.models import Tienda
from users.models import User

from .forms import CheckoutAddressForm, CheckoutBuyerForm, CheckoutPaymentForm, OrderLookupForm, PedidoEstadoForm
from .models import Pedido
from .utils import build_cart_snapshot, create_order_from_checkout, process_secure_payment


def _checkout_session(request):
	return request.session.setdefault('checkout', {})


def _clear_checkout_session(request):
	request.session.pop('checkout', None)
	request.session.pop('checkout_order_id', None)


def _guest_order_codes(request):
	return request.session.get('guest_order_codes', [])


def _remember_guest_order_code(request, codigo_pedido):
	guest_codes = list(_guest_order_codes(request))
	if codigo_pedido not in guest_codes:
		guest_codes.append(codigo_pedido)
	request.session['guest_order_codes'] = guest_codes
	request.session.modified = True


def _order_base_queryset():
	return Pedido.objects.select_related('usuario').prefetch_related('items__producto', 'items__producto__tienda')


def _buyer_orders_for_request(request):
	if request.user.is_authenticated:
		return _order_base_queryset().filter(usuario=request.user)
	guest_codes = _guest_order_codes(request)
	if not guest_codes:
		return _order_base_queryset().none()
	return _order_base_queryset().filter(codigo_pedido__in=guest_codes)


def _order_visible_to_request(request, pedido):
	if request.user.is_authenticated:
		return pedido.usuario_id == request.user.id
	return pedido.codigo_pedido in _guest_order_codes(request)


def _vendor_orders_for_user(user):
	orders = _order_base_queryset()
	if user.is_staff or user.rol == User.Role.ADMIN:
		return orders.distinct()
	if not _is_seller(user):
		return orders.none()
	store = getattr(user, 'tienda', None)
	if store is None:
		return orders.none()
	return orders.filter(items__producto__tienda=store).distinct()


def _vendor_order_visible_to_user(user, pedido):
	if user.is_staff or user.rol == User.Role.ADMIN:
		return True
	if not _is_seller(user):
		return False
	store = getattr(user, 'tienda', None)
	if store is None:
		return False
	return pedido.items.filter(producto__tienda=store).exists()


def _vendor_order_items(pedido, user):
	if user.is_staff or user.rol == User.Role.ADMIN:
		return pedido.items.select_related('producto', 'producto__tienda').all()
	store = getattr(user, 'tienda', None)
	if store is None:
		return pedido.items.none()
	return pedido.items.select_related('producto', 'producto__tienda').filter(producto__tienda=store)


@buyer_or_guest_required
@require_http_methods(["GET", "POST"])
def checkout_customer(request):
	checkout_session = _checkout_session(request)
	form = CheckoutBuyerForm(request.POST or None, user=request.user)

	if request.method == 'POST' and form.is_valid():
		checkout_session['buyer'] = form.cleaned_data
		request.session.modified = True
		return redirect('checkout_address')

	return render(
		request,
		'orders/checkout_step.html',
		{
			'step_title': 'Datos del comprador',
			'step_description': 'Confirma tus datos antes de continuar con una compra protegida y trazable.',
			'security_note': 'Usamos estos datos para preparar el pedido y mantener la comunicación segura durante el checkout.',
			'form': form,
			'next_label': 'Continuar con direcciones',
			'step_index': 1,
			'step_total': 3,
		},
	)


@buyer_or_guest_required
@require_http_methods(["GET", "POST"])
def checkout_address(request):
	checkout_session = _checkout_session(request)
	if 'buyer' not in checkout_session:
		messages.info(request, 'Completa primero los datos del comprador.')
		return redirect('checkout_customer')

	form = CheckoutAddressForm(request.POST or None, user=request.user)

	if request.method == 'POST' and form.is_valid():
		checkout_session['address'] = form.cleaned_data
		request.session.modified = True
		return redirect('checkout_payment')

	return render(
		request,
		'orders/checkout_step.html',
		{
			'step_title': 'Direcciones de envío y facturación',
			'step_description': 'Introduce una dirección clara para que el pedido llegue correctamente y quede registrado con precisión.',
			'security_note': 'La información de entrega y facturación se guarda para el pedido y se muestra antes del pago final.',
			'form': form,
			'next_label': 'Continuar al pago',
			'step_index': 2,
			'step_total': 3,
		},
	)


@buyer_or_guest_required
@require_http_methods(["GET", "POST"])
def checkout_payment(request):
	checkout_session = _checkout_session(request)
	if 'buyer' not in checkout_session:
		messages.info(request, 'Completa primero los datos del comprador.')
		return redirect('checkout_customer')
	if 'address' not in checkout_session:
		messages.info(request, 'Completa primero las direcciones de envío y facturación.')
		return redirect('checkout_address')

	cart_snapshot = build_cart_snapshot(request)
	if not cart_snapshot['items']:
		messages.error(request, 'Tu carrito está vacío.')
		return redirect('cart_view')

	form = CheckoutPaymentForm(request.POST or None)

	if request.method == 'POST' and form.is_valid():
		pedido = create_order_from_checkout(
			user=request.user,
			buyer_data=checkout_session['buyer'],
			address_data=checkout_session['address'],
			payment_method=form.cleaned_data['metodo_pago'],
			cart_snapshot=cart_snapshot,
		)
		payment_result = process_secure_payment(pedido, form.cleaned_data['metodo_pago'])

		if payment_result['success']:
			pedido.estado = 'preparacion'
			pedido.save(update_fields=['estado', 'updated_at'])
			request.session.pop('cart', None)
			if request.user.is_authenticated:
				carrito = request.user.carrito if hasattr(request.user, 'carrito') else None
				if carrito:
					carrito.items.all().delete()
			_clear_checkout_session(request)
			request.session['last_order_code'] = pedido.codigo_pedido
			if request.session.get('guest') == True:
				_remember_guest_order_code(request, pedido.codigo_pedido)
			messages.success(request, 'Pago confirmado. Tu pedido se ha completado con éxito en un entorno seguro.')
			return redirect('checkout_complete')

		messages.error(request, 'No se ha podido completar el pago.')

	return render(
		request,
		'orders/checkout_step.html',
		{
			'step_title': 'Pago',
			'step_description': 'Elige contra reembolso o pasarela de pago segura. Este es el último paso de la compra.',
			'security_note': 'La pasarela está simulada con una función siempre exitosa para mantener un flujo estable y seguro.',
			'form': form,
			'summary': cart_snapshot,
			'next_label': 'Confirmar pago',
			'step_index': 3,
			'step_total': 3,
		},
	)


@buyer_or_guest_required
def checkout_complete(request):
	pedido = None
	last_order_code = request.session.get('last_order_code')
	if last_order_code:
		pedido = Pedido.objects.filter(codigo_pedido=last_order_code).prefetch_related('items', 'items__producto').first()

	return render(
		request,
		'orders/checkout_complete.html',
		{
			'order': pedido,
		},
	)


@buyer_or_guest_required
def order_history(request):
	orders = _buyer_orders_for_request(request).order_by('-created_at')
	lookup_form = OrderLookupForm()
	return render(
		request,
		'orders/order_history.html',
		{
			'orders': orders,
			'lookup_form': lookup_form,
			'is_guest': not request.user.is_authenticated,
		},
	)


@buyer_or_guest_required
@require_http_methods(["POST"])
def order_lookup(request):
	form = OrderLookupForm(request.POST)
	if not form.is_valid():
		messages.error(request, 'Introduce un código de pedido válido.')
		return redirect('order_history')

	codigo_pedido = form.cleaned_data['codigo_pedido']
	pedido = _order_base_queryset().filter(codigo_pedido=codigo_pedido).first()
	if not pedido or not _order_visible_to_request(request, pedido):
		messages.error(request, 'No se ha encontrado ningún pedido con ese código.')
		return redirect('order_history')

	return redirect('order_detail', codigo_pedido=pedido.codigo_pedido)


@buyer_or_guest_required
def order_detail(request, codigo_pedido):
	pedido = get_object_or_404(_order_base_queryset(), codigo_pedido=codigo_pedido)
	if not _order_visible_to_request(request, pedido):
		raise Http404

	return render(
		request,
		'orders/order_detail.html',
		{
			'order': pedido,
			'order_items': pedido.items.select_related('producto', 'producto__tienda').all(),
			'can_edit_status': False,
		},
	)


@login_required
def vendor_order_list(request):
	if not (_is_seller(request.user) or request.user.is_staff or request.user.rol == User.Role.ADMIN):
		return redirect('account_detail')

	selected_store_id = (request.GET.get('tienda') or '').strip()
	selected_store = None
	if selected_store_id:
		selected_store = Tienda.objects.filter(pk=selected_store_id).first()
	elif getattr(request.user, 'tienda', None):
		selected_store = request.user.tienda

	if selected_store is not None:
		if request.user.is_staff or request.user.rol == User.Role.ADMIN:
			allowed = True
		else:
			user_store = getattr(request.user, 'tienda', None)
			allowed = bool(user_store and user_store.pk == selected_store.pk)
		if not allowed:
			selected_store = getattr(request.user, 'tienda', None)

	orders = _vendor_orders_for_user(request.user)
	if selected_store is not None:
		orders = orders.filter(items__producto__tienda=selected_store).distinct()

	search_code = (request.GET.get('codigo_pedido') or '').strip().upper()
	user_filter = (request.GET.get('usuario') or '').strip()

	if search_code:
		orders = orders.filter(codigo_pedido__icontains=search_code)
	if user_filter:
		orders = orders.filter(Q(usuario__email__icontains=user_filter) | Q(usuario__nombre__icontains=user_filter) | Q(usuario__apellidos__icontains=user_filter) | Q(comprador_email__icontains=user_filter) | Q(comprador_nombre__icontains=user_filter) | Q(comprador_apellidos__icontains=user_filter))

	if request.user.is_staff or request.user.rol == User.Role.ADMIN:
		buyers = User.objects.filter(pedidos__isnull=False).order_by('email').distinct()
	else:
		store = selected_store or getattr(request.user, 'tienda', None)
		buyers = User.objects.filter(pedidos__items__producto__tienda=store).order_by('email').distinct() if store else User.objects.none()

	return render(
		request,
		'orders/vendor_order_list.html',
		{
			'orders': orders.order_by('-created_at'),
			'buyers': buyers,
			'current_code': search_code,
			'current_user_filter': user_filter,
			'selected_store': selected_store,
		},
	)


@login_required
def vendor_order_detail(request, codigo_pedido):
	if not (_is_seller(request.user) or request.user.is_staff or request.user.rol == User.Role.ADMIN):
		return redirect('account_detail')

	pedido = get_object_or_404(_order_base_queryset(), codigo_pedido=codigo_pedido)
	if not _vendor_order_visible_to_user(request.user, pedido):
		raise Http404

	selected_store_id = (request.GET.get('tienda') or '').strip()
	selected_store = None
	if selected_store_id:
		selected_store = Tienda.objects.filter(pk=selected_store_id).first()
	if selected_store is None and getattr(request.user, 'tienda', None):
		selected_store = request.user.tienda
	if selected_store is not None and not (request.user.is_staff or request.user.rol == User.Role.ADMIN):
		if not pedido.items.filter(producto__tienda=selected_store).exists():
			raise Http404

	if request.method == 'POST':
		form = PedidoEstadoForm(request.POST, instance=pedido)
		if form.is_valid():
			form.save()
			messages.success(request, 'El estado del pedido se ha actualizado correctamente.')
			redirect_target = f"{reverse('vendor_order_detail', kwargs={'codigo_pedido': pedido.codigo_pedido})}?tienda={selected_store.pk}" if selected_store else reverse('vendor_order_detail', kwargs={'codigo_pedido': pedido.codigo_pedido})
			return redirect(redirect_target)
	else:
		form = PedidoEstadoForm(instance=pedido)

	return render(
		request,
		'orders/order_detail.html',
		{
			'order': pedido,
			'order_items': _vendor_order_items(pedido, request.user),
			'can_edit_status': True,
			'status_form': form,
			'selected_store': selected_store,
		},
	)
