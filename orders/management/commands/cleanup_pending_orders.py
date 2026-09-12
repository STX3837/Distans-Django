import stripe
from django.core.management.base import BaseCommand
from django.utils import timezone
from orders.models import Pedido
from orders.utils import cancel_pending_payment


class Command(BaseCommand):
    help = 'Cierra pagos abandonados y libera su stock cuando Stripe permite cancelarlos.'

    def handle(self, *args, **options):
        orders = Pedido.objects.filter(estado='pendiente_pago', stock_reservado=True, reserva_expira__lte=timezone.now())
        for order in orders.iterator():
            try:
                cancel_pending_payment(order)
            except (RuntimeError, stripe.error.StripeError) as exc:
                self.stderr.write(f'Pedido {order.codigo_pedido}: se conserva la reserva ({type(exc).__name__}).')
