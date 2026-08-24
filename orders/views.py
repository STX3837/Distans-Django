from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from products.views import buyer_or_guest_required

from .forms import CheckoutAddressForm, CheckoutBuyerForm, CheckoutPaymentForm
from .models import Pedido
from .utils import build_cart_snapshot, create_order_from_checkout, process_secure_payment


def _checkout_session(request):
	return request.session.setdefault('checkout', {})


def _clear_checkout_session(request):
	request.session.pop('checkout', None)
	request.session.pop('checkout_order_id', None)


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
			pedido.estado = 'completado'
			pedido.save(update_fields=['estado', 'updated_at'])
			request.session.pop('cart', None)
			if request.user.is_authenticated:
				carrito = request.user.carrito if hasattr(request.user, 'carrito') else None
				if carrito:
					carrito.items.all().delete()
			_clear_checkout_session(request)
			request.session['last_order_code'] = pedido.codigo_pedido
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
