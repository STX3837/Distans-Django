from django.db import migrations, models
import django.db.models.deletion


def preserve_store(apps, schema_editor):
    Producto = apps.get_model('products', 'Producto')
    Line = apps.get_model('orders', 'ProductoPedido')
    db = schema_editor.connection.alias
    for product in Producto.objects.using(db).only('id', 'tienda_id').iterator():
        Line.objects.using(db).filter(producto_id=product.pk).update(tienda_id=product.tienda_id)


class Migration(migrations.Migration):
    dependencies = [('orders', '0006_payment_state'), ('stores', '0009_stripe_subscription')]
    operations = [
        migrations.AddField(model_name='productopedido', name='tienda', field=models.ForeignKey(to='stores.tienda', on_delete=django.db.models.deletion.SET_NULL, null=True, blank=True, related_name='lineas_pedido')),
        migrations.RunPython(preserve_store, migrations.RunPython.noop),
    ]
