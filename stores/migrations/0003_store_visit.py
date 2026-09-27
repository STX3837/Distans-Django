from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('stores', '0002_tienda_latitud_longitud'),
    ]

    operations = [
        migrations.CreateModel(
            name='VisitaTienda',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('session_key', models.CharField(blank=True, max_length=40)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('tienda', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='visitas', to='stores.tienda')),
            ],
            options={
                'indexes': [models.Index(fields=['tienda', 'created_at'], name='stores_vis_tienda_6b7e8e_idx')],
            },
        ),
    ]