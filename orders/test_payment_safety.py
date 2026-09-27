from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch
from unittest import skipUnless
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.core.management import call_command
from django.test import TestCase, TransactionTestCase, RequestFactory, override_settings
from django.db import connection, connections, close_old_connections
from django.urls import reverse
from django.utils import timezone

from products.models import Producto
from stores.models import Tienda
from stores.utils import online_store_filter
from users.models import User
from .models import Pedido
from .utils import (build_cart_snapshot, create_order_from_checkout,
                    mark_order_as_paid, release_order_stock_reservation, cancel_pending_payment,
                    activate_premium_store, create_premium_checkout_session)


@override_settings(STRIPE_SECRET_KEY='sk_test_fake', STRIPE_WEBHOOK_SECRET='whsec_fake')
class PaymentSafetyTests(TestCase):
    def setUp(self):
        self.seller = User.objects.create_user(email='safety@example.com', password='test', nombre='Seller', apellidos='Test', rol=User.Role.SELLER)
        self.store = Tienda.objects.create(nombre='Safety store', vendedor=self.seller)
        self.product = Producto.objects.create(nombre='Safety product', descripcion='Test', precio=Decimal('10'), marca='Test', categoria='hogar_bricolaje', stock=5, tienda=self.store)
        self.request = RequestFactory().get('/')
        self.request.user = SimpleNamespace(is_authenticated=False)
        self.request.session = {'cart': {str(self.product.pk): {'id': self.product.pk, 'cantidad': 2}}}

    def order(self, method='pasarela', snapshot=None):
        return create_order_from_checkout(
            user=None, buyer_data={'nombre': 'Buyer', 'apellidos': 'Test', 'email': 'buyer@example.com', 'telefono': '600123123'},
            address_data={key: value for key, value in [
                ('direccion_envio', 'Calle 1'), ('ciudad_envio', 'Madrid'), ('codigo_postal_envio', '28001'),
                ('direccion_facturacion', 'Calle 1'), ('ciudad_facturacion', 'Madrid'), ('codigo_postal_facturacion', '28001')]},
            payment_method=method, cart_snapshot=snapshot or build_cart_snapshot(self.request))

    def webhook(self, event_type, obj):
        with patch('orders.views.stripe.Webhook.construct_event', return_value={'type': event_type, 'data': {'object': obj}}):
            return self.client.post(reverse('stripe_webhook'), data='{}', content_type='application/json')

    def test_cod_cancel_restores_stock_once_without_recording_a_collection(self):
        order = self.order('contrarrembolso')
        self.assertEqual(order.estado_pago, 'cobro_tienda')
        self.assertEqual(order.estado, 'preparacion')
        self.client.force_login(self.seller)
        url = reverse('vendor_order_detail', args=[order.codigo_pedido])
        self.assertEqual(self.client.post(url, {'estado': 'cancelado'}).status_code, 302)
        self.client.post(url, {'estado': 'cancelado'})
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 5)

    def test_paid_notification_does_not_reset_shipping_or_restore_stock(self):
        order = self.order()
        mark_order_as_paid(order)
        Pedido.objects.filter(pk=order.pk).update(estado='enviado')
        mark_order_as_paid(order)
        release_order_stock_reservation(order)
        order.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(order.estado, 'enviado')
        self.assertEqual(order.estado_pago, 'pagado')
        self.assertEqual(self.product.stock, 3)

    def test_duplicate_expiration_restores_stock_once_with_deleted_product(self):
        order = self.order()
        self.product.delete()
        release_order_stock_reservation(order)
        release_order_stock_reservation(order)
        order.refresh_from_db()
        self.assertEqual(order.estado, 'cancelado')
        self.client.force_login(self.seller)
        self.assertEqual(self.client.get(reverse('vendor_order_detail', args=[order.codigo_pedido])).status_code, 200)

    def test_unpaid_checkout_completion_does_not_confirm_payment(self):
        order = self.order()
        order.stripe_checkout_session_id = 'cs_safety'
        order.save()
        self.assertEqual(self.webhook('checkout.session.completed', {'id': 'cs_safety', 'payment_status': 'unpaid'}).status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.estado_pago, 'pendiente')
        self.webhook('checkout.session.async_payment_succeeded', {'id': 'cs_safety', 'payment_status': 'paid'})
        order.refresh_from_db()
        self.assertEqual(order.estado_pago, 'pagado')
        self.assertEqual(order.estado, 'preparacion')

    def test_late_payment_keeps_cancelled_order_and_flags_refund(self):
        order = self.order()
        release_order_stock_reservation(order)
        mark_order_as_paid(order)
        order.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(order.estado, 'cancelado')
        self.assertEqual(order.estado_pago, 'reembolso_pendiente')
        self.assertEqual(self.product.stock, 5)

    @patch('orders.utils.stripe.checkout.Session.expire')
    @patch('orders.utils.get_stripe_session')
    def test_cancel_closes_checkout_before_releasing_stock(self, retrieve, expire):
        order = self.order()
        order.stripe_checkout_session_id = 'cs_safety'
        order.save()
        retrieve.return_value = SimpleNamespace(id='cs_safety', payment_status='unpaid', status='open')
        def expire_session(session_id):
            self.product.refresh_from_db()
            self.assertEqual(self.product.stock, 3)
        expire.side_effect = expire_session
        self.assertTrue(cancel_pending_payment(order))
        expire.assert_called_once_with('cs_safety')
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 5)

    @patch('orders.utils.get_stripe_session')
    def test_processing_payment_keeps_reservation(self, retrieve):
        order = self.order()
        order.stripe_checkout_session_id = 'cs_processing'
        order.save()
        retrieve.return_value = SimpleNamespace(payment_status='unpaid', status='complete')
        self.assertFalse(cancel_pending_payment(order))
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 3)

    def test_cleanup_only_cancels_expired_pending_orders(self):
        order = self.order()
        call_command('cleanup_pending_orders')
        order.refresh_from_db()
        self.assertEqual(order.estado, 'pendiente_pago')
        Pedido.objects.filter(pk=order.pk).update(reserva_expira=timezone.now() - timedelta(seconds=1))
        call_command('cleanup_pending_orders')
        order.refresh_from_db()
        self.assertEqual(order.estado, 'cancelado')

    def test_repeated_expiration_with_existing_product_restores_exact_quantity(self):
        order = self.order()
        release_order_stock_reservation(order)
        release_order_stock_reservation(order)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 5)

    @patch('orders.utils.get_stripe_session')
    def test_already_paid_checkout_cannot_be_cancelled_as_abandoned(self, retrieve):
        order = self.order()
        order.stripe_checkout_session_id = 'cs_paid'
        order.save()
        retrieve.return_value = SimpleNamespace(payment_status='paid', status='complete')
        self.assertFalse(cancel_pending_payment(order))
        order.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(order.estado_pago, 'pagado')
        self.assertEqual(self.product.stock, 3)

    def test_checkout_revalidates_stock_and_price(self):
        snapshot = build_cart_snapshot(self.request)
        Producto.objects.filter(pk=self.product.pk).update(stock=1)
        with self.assertRaises(ValueError):
            self.order(snapshot=snapshot)
        self.assertFalse(Pedido.objects.exists())
        Producto.objects.filter(pk=self.product.pk).update(stock=5, precio=Decimal('12'))
        with self.assertRaises(ValueError):
            self.order(snapshot=snapshot)
        self.assertFalse(Pedido.objects.exists())

    @patch('orders.utils.stripe.Subscription.retrieve')
    def test_premium_renewal_failure_and_recovery_follow_current_stripe_state(self, retrieve):
        end = int((timezone.now() + timedelta(days=31)).timestamp())
        subscription = {'id': 'sub_safety', 'status': 'active', 'metadata': {'tipo': 'suscripcion_premium', 'tienda_id': str(self.store.pk)}, 'items': {'data': [{'current_period_end': end}]}}
        retrieve.return_value = subscription
        activate_premium_store(self.store, 'sub_safety')
        self.store.refresh_from_db()
        self.assertEqual(int(self.store.premium_hasta.timestamp()), end)
        self.assertTrue(self.store.permite_compra_online)
        subscription['status'] = 'past_due'
        self.webhook('invoice.payment_failed', {'id': 'in_fail', 'parent': {'subscription_details': {'subscription': 'sub_safety'}}})
        self.store.refresh_from_db()
        self.assertFalse(self.store.permite_compra_online)
        subscription['status'] = 'active'
        self.webhook('invoice.paid', {'id': 'in_paid', 'subscription': 'sub_safety'})
        self.store.refresh_from_db()
        self.assertTrue(self.store.permite_compra_online)
        subscription['status'] = 'canceled'
        self.webhook('customer.subscription.deleted', subscription)
        self.store.refresh_from_db()
        self.assertFalse(self.store.permite_compra_online)

    def test_online_filters_exclude_expired_local_and_stripe_subscriptions(self):
        self.store.fecha_renovacion = timezone.localdate() - timedelta(days=1)
        self.store.save()
        self.assertFalse(Tienda.objects.filter(online_store_filter()).exists())
        self.store.stripe_subscription_id = 'sub_expired'
        self.store.premium_hasta = timezone.now() - timedelta(seconds=1)
        self.store.fecha_renovacion = timezone.localdate() + timedelta(days=1)
        self.store.save()
        self.assertFalse(Tienda.objects.filter(online_store_filter()).exists())
        self.assertFalse(self.store.permite_compra_online)

    @patch('orders.utils.stripe.checkout.Session.retrieve')
    @patch('orders.utils.stripe.checkout.Session.create')
    def test_premium_checkout_reuses_open_session(self, create, retrieve):
        create.return_value = SimpleNamespace(id='cs_premium', url='https://example.com')
        retrieve.return_value = SimpleNamespace(id='cs_premium', status='open')
        create_premium_checkout_session(self.request, self.store)
        create_premium_checkout_session(self.request, self.store)
        create.assert_called_once()


@skipUnless(connection.vendor == 'postgresql', 'Los bloqueos de filas requieren PostgreSQL.')
class ConcurrentStockTests(TransactionTestCase):
    setUp = PaymentSafetyTests.setUp
    order = PaymentSafetyTests.order

    def test_two_buyers_cannot_reserve_the_same_last_units(self):
        self.request.session['cart'][str(self.product.pk)]['cantidad'] = 4
        snapshot = build_cart_snapshot(self.request)
        barrier = Barrier(2)

        def buy():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                self.order(snapshot=snapshot)
                return 'accepted'
            except ValueError:
                return 'insufficient_stock'
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(buy) for _ in range(2)]
            results = [future.result(timeout=20) for future in futures]
        self.assertCountEqual(results, ['accepted', 'insufficient_stock'])
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 1)
        self.assertEqual(Pedido.objects.count(), 1)
