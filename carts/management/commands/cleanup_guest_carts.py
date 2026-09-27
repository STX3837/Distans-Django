from django.contrib.sessions.models import Session
from django.core.management.base import BaseCommand
from django.db.models import Subquery
from django.utils import timezone

from carts.models import Carrito


class Command(BaseCommand):
    help = (
        "Elimina carritos de invitados cuya sesion ya no existe "
        "o cuya sesion ha expirado."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Muestra cuántos carritos se eliminarían sin borrar datos.",
        )

    def handle(self, *args, **options):
        now = timezone.now()

        valid_session_keys = Session.objects.filter(expire_date__gt=now).values("session_key")
        stale_guest_carts = Carrito.objects.filter(usuario__isnull=True).exclude(
            sesion__in=Subquery(valid_session_keys)
        )

        total = stale_guest_carts.count()

        if options["dry_run"]:
            self.stdout.write(
                self.style.WARNING(
                    f"[DRY RUN] Se eliminarian {total} carritos de invitado obsoletos."
                )
            )
            return

        deleted, _ = stale_guest_carts.delete()
        self.stdout.write(
            self.style.SUCCESS(
                f"Eliminados {deleted} registros de carritos de invitado obsoletos."
            )
        )
