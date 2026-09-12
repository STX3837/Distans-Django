from datetime import timedelta
from django.db import migrations, models
from django.utils import timezone


def migrate_states(apps, schema_editor):
    Pedido = apps.get_model('orders', 'Pedido')
    db = schema_editor.connection.alias
    orders = Pedido.objects.using(db)
    orders.exclude(estado='cancelado').update(stock_descontado=True)
    orders.filter(estado='cancelado').update(estado_pago='cancelado')
    orders.filter(metodo_pago='contrarrembolso').exclude(estado='cancelado').update(estado_pago='cobro_tienda', stock_reservado=False)
    orders.filter(metodo_pago='contrarrembolso', estado__in=['completado', 'pendiente_pago']).update(estado='preparacion')
    orders.filter(metodo_pago='pasarela').exclude(estado__in=['cancelado', 'pendiente_pago']).update(estado_pago='pagado')
    orders.filter(metodo_pago='pasarela', estado='completado').update(estado='preparacion')
    orders.filter(estado='pendiente_pago', stock_reservado=True).update(reserva_expira=timezone.now() + timedelta(minutes=35))


class Migration(migrations.Migration):
    dependencies = [('orders', '0005_productopedido_nombre_producto_and_more')]
    operations = [
        migrations.AddField(model_name='pedido', name='estado_pago', field=models.CharField(max_length=25, default='pendiente', choices=[('pendiente', 'Pendiente de pago'), ('pagado', 'Pagado online'), ('cobro_tienda', 'Cobro al entregar, gestionado por la tienda'), ('cancelado', 'Pago cancelado'), ('reembolso_pendiente', 'Reembolso online pendiente')])),
        migrations.AddField(model_name='pedido', name='reserva_expira', field=models.DateTimeField(null=True, blank=True)),
        migrations.AddField(model_name='pedido', name='stock_descontado', field=models.BooleanField(default=False)),
        migrations.RunPython(migrate_states, migrations.RunPython.noop),
    ]
