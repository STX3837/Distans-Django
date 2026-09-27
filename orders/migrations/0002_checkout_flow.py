import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='pedido',
            name='estado',
            field=models.CharField(choices=[('pendiente_pago', 'Pendiente de pago'), ('completado', 'Completado'), ('cancelado', 'Cancelado')], default='pendiente_pago', max_length=20),
        ),
        migrations.AlterField(
            model_name='pedido',
            name='fecha',
            field=models.DateField(default=django.utils.timezone.localdate),
        ),
        migrations.AlterField(
            model_name='pedido',
            name='metodo_pago',
            field=models.CharField(choices=[('contrarrembolso', 'Contrarrembolso'), ('pasarela', 'Pasarela de pago segura')], max_length=20),
        ),
        migrations.AlterField(
            model_name='pedido',
            name='usuario',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='pedidos', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='pedido',
            name='comprador_apellidos',
            field=models.CharField(default='', max_length=150),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='pedido',
            name='comprador_email',
            field=models.EmailField(default='', max_length=254),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='pedido',
            name='comprador_nombre',
            field=models.CharField(default='', max_length=150),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='pedido',
            name='codigo_postal_envio',
            field=models.CharField(default='', max_length=20),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='pedido',
            name='codigo_postal_facturacion',
            field=models.CharField(default='', max_length=20),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='pedido',
            name='ciudad_envio',
            field=models.CharField(default='', max_length=100),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='pedido',
            name='ciudad_facturacion',
            field=models.CharField(default='', max_length=100),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='pedido',
            name='descuento',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
    ]