from django.core.management.base import BaseCommand
from django.utils import timezone

from stores.models import Tienda


class Command(BaseCommand):
    help = 'Desactiva tiendas Premium cuya suscripcion ha caducado.'

    def handle(self, *args, **options):
        expired_stores = Tienda.objects.filter(
            plan=Tienda.Plan.PREMIUM,
            suscripcion_activa=True,
            fecha_renovacion__lt=timezone.localdate(),
        )
        total = expired_stores.update(
            plan=Tienda.Plan.FREEMIUM,
            suscripcion_activa=False,
            pasarela_activa=False,
            updated_at=timezone.now(),
        )
        self.stdout.write(self.style.SUCCESS(f'{total} tiendas Premium caducadas.'))
