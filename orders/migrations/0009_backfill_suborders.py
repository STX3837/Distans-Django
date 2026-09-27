from django.db import migrations


def create_suborders(apps, schema_editor):
    Subpedido = apps.get_model('orders', 'Subpedido')
    ProductoPedido = apps.get_model('orders', 'ProductoPedido')

    groups = (
        ProductoPedido.objects.exclude(tienda_id=None)
        .values_list('pedido_id', 'tienda_id', 'nombre_tienda')
        .distinct()
    )
    for pedido_id, tienda_id, nombre_tienda in groups.iterator():
        first_line = ProductoPedido.objects.filter(pedido_id=pedido_id, tienda_id=tienda_id).first()
        parent_state = first_line.pedido.estado
        if parent_state == 'cancelado':
            state = 'cancelado'
        elif parent_state in {'enviado', 'entregado'}:
            state = 'recogido'
        else:
            state = 'preparacion'
        suborder, _ = Subpedido.objects.get_or_create(
            pedido_id=pedido_id,
            tienda_id=tienda_id,
            defaults={'nombre_tienda': nombre_tienda or '', 'estado': state},
        )
        ProductoPedido.objects.filter(
            pedido_id=pedido_id, tienda_id=tienda_id, subpedido_id=None
        ).update(subpedido_id=suborder.pk)


def remove_suborder_links(apps, schema_editor):
    ProductoPedido = apps.get_model('orders', 'ProductoPedido')
    ProductoPedido.objects.update(subpedido_id=None)


class Migration(migrations.Migration):
    dependencies = [('orders', '0008_productopedido_cancelado_productopedido_cancelado_at_and_more')]

    operations = [migrations.RunPython(create_suborders, remove_suborder_links)]
