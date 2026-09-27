from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0005_producto_en_oferta'),
    ]

    operations = [
        migrations.CreateModel(
            name='VisitaProducto',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('session_key', models.CharField(blank=True, max_length=40)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('producto', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='visitas', to='products.producto')),
            ],
            options={
                'indexes': [models.Index(fields=['producto', 'created_at'], name='products_vi_product_8d4d3b_idx')],
            },
        ),
    ]