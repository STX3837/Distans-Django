from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from urllib.parse import unquote

import stripe
from django.conf import settings

from products.views import buyer_or_guest_required

from .forms import CheckoutAddressForm, CheckoutBuyerForm, CheckoutPaymentForm
from .models import Pedido
from .utils import (
	build_cart_snapshot,
	create_order_from_checkout,
	create_stripe_checkout_session,
	get_stripe_session,
	mark_order_as_paid,
	process_secure_payment,
	release_order_stock_reservation,
)


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
		previous_order_id = checkout_session.get('order_id') or request.session.get('checkout_order_id')
		if previous_order_id:
			previous_order = Pedido.objects.filter(pk=previous_order_id, estado='pendiente_pago').first()
			if previous_order:
				release_order_stock_reservation(previous_order)

		try:
			pedido = create_order_from_checkout(
				user=request.user,
				buyer_data=checkout_session['buyer'],
				address_data=checkout_session['address'],
				payment_method=form.cleaned_data['metodo_pago'],
				cart_snapshot=cart_snapshot,
			)
		except ValueError as exc:
			messages.error(request, str(exc))
			return redirect('cart_view')

		if form.cleaned_data['metodo_pago'] == 'pasarela':
			request.session['checkout_order_id'] = pedido.pk
			request.session.modified = True
			try:
				session = create_stripe_checkout_session(request, pedido)
			except RuntimeError as exc:
				release_order_stock_reservation(pedido)
				messages.error(request, str(exc))
				return redirect('checkout_payment')
			except stripe.error.StripeError:
				release_order_stock_reservation(pedido)
				messages.error(request, 'No se ha podido iniciar el pago con Stripe. Inténtalo de nuevo.')
				return redirect('checkout_payment')
			return redirect(session.url)

		payment_result = process_secure_payment(pedido, form.cleaned_data['metodo_pago'])
		if payment_result['success']:
			mark_order_as_paid(pedido)
			request.session.pop('cart', None)
			if request.user.is_authenticated:
				carrito = request.user.carrito if hasattr(request.user, 'carrito') else None
				if carrito:
					carrito.items.all().delete()
			_clear_checkout_session(request)
			request.session['last_order_code'] = pedido.codigo_pedido
			messages.success(request, 'Pago confirmado. Tu pedido se ha completado con éxito en un entorno seguro.')
			return redirect('checkout_complete')

		release_order_stock_reservation(pedido)
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
def checkout_payment_success(request):
	session_id = unquote(request.GET.get('session_id', ''))
	placeholder_values = {'{CHECKOUT_SESSION_ID}', 'CHECKOUT_SESSION_ID'}
	if not session_id or session_id in placeholder_values:
		pending_order_id = request.session.get('checkout_order_id')
		pending_order = Pedido.objects.filter(pk=pending_order_id, estado='pendiente_pago').first()
		if pending_order and pending_order.stripe_checkout_session_id:
			session_id = pending_order.stripe_checkout_session_id

	if not session_id or session_id in placeholder_values:
		messages.error(request, 'No se ha recibido confirmación de pago.')
		return redirect('checkout_payment')

	try:
		stripe_session = get_stripe_session(session_id)
	except RuntimeError as exc:
		messages.error(request, str(exc))
		return redirect('checkout_payment')
	except stripe.error.StripeError:
		messages.error(request, 'No se ha podido validar el pago con Stripe.')
		return redirect('checkout_payment')

	if stripe_session.payment_status != 'paid':
		messages.error(request, 'El pago no está confirmado todavía.')
		return redirect('checkout_payment')

	pedido = Pedido.objects.filter(stripe_checkout_session_id=session_id).first()
	if not pedido:
		messages.error(request, 'No se ha encontrado el pedido asociado al pago.')
		return redirect('checkout_payment')

	mark_order_as_paid(pedido)
	request.session.pop('cart', None)
	if request.user.is_authenticated:
		carrito = request.user.carrito if hasattr(request.user, 'carrito') else None
		if carrito:
			carrito.items.all().delete()
	_clear_checkout_session(request)
	request.session['last_order_code'] = pedido.codigo_pedido
	messages.success(request, 'Pago confirmado por Stripe. Tu pedido se ha completado correctamente.')
	return redirect('checkout_complete')


@buyer_or_guest_required
def checkout_payment_cancel(request):
	pedido_id = request.GET.get('pedido_id') or request.session.get('checkout_order_id')
	if pedido_id:
		pedido = Pedido.objects.filter(pk=pedido_id).first()
		if pedido:
			release_order_stock_reservation(pedido)

	messages.warning(request, 'Has cancelado el pago. La reserva de stock se ha liberado.')
	return redirect('checkout_payment')


@csrf_exempt
@require_http_methods(["POST"])
def stripe_webhook(request):
	if not settings.STRIPE_WEBHOOK_SECRET or not settings.STRIPE_SECRET_KEY:
		return HttpResponse(status=400)

	stripe.api_key = settings.STRIPE_SECRET_KEY
	payload = request.body
	signature = request.META.get('HTTP_STRIPE_SIGNATURE', '')

	try:
		event = stripe.Webhook.construct_event(payload, signature, settings.STRIPE_WEBHOOK_SECRET)
	except (ValueError, stripe.error.SignatureVerificationError):
		return HttpResponse(status=400)

	event_type = event.get('type')
	data_object = event.get('data', {}).get('object', {})
	session_id = data_object.get('id')

	if not session_id:
		return HttpResponse(status=200)

	pedido = Pedido.objects.filter(stripe_checkout_session_id=session_id).first()
	if not pedido:
		return HttpResponse(status=200)

	if event_type == 'checkout.session.completed':
		mark_order_as_paid(pedido)
	elif event_type in {'checkout.session.expired', 'checkout.session.async_payment_failed'}:
		release_order_stock_reservation(pedido)

	return HttpResponse(status=200)
