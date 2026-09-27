from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0003_pedido_stripe_and_stock_reservation'),
    ]

    operations = [
        migrations.AlterField(
            model_name='pedido',
            name='estado',
            field=models.CharField(
                choices=[
                    ('pendiente_pago', 'Pendiente de pago'),
                    ('completado', 'Completado'),
                    ('preparacion', 'En preparación'),
                    ('enviado', 'Enviado'),
                    ('entregado', 'Entregado'),
                    ('cancelado', 'Cancelado'),
                ],
                default='preparacion',
                max_length=20,
            ),
        ),
    ]
