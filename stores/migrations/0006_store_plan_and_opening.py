from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stores', '0005_allow_guest_visits'),
    ]

    operations = [
        migrations.AddField(
            model_name='tienda',
            name='fecha_alta',
            field=models.DateField(auto_now_add=True, null=True),
        ),
        migrations.AddField(
            model_name='tienda',
            name='fecha_renovacion',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='tienda',
            name='informacion_apertura',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='tienda',
            name='plan',
            field=models.CharField(choices=[('freemium', 'Freemium'), ('premium', 'Premium')], default='premium', max_length=10),
        ),
        migrations.AddField(
            model_name='tienda',
            name='suscripcion_activa',
            field=models.BooleanField(default=True),
        ),
    ]
