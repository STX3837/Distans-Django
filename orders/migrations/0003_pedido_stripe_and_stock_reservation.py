from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0002_checkout_flow'),
    ]

    operations = [
        migrations.AddField(
            model_name='pedido',
            name='stock_reservado',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='pedido',
            name='stripe_checkout_session_id',
            field=models.CharField(blank=True, db_index=True, max_length=255, null=True),
        ),
    ]
