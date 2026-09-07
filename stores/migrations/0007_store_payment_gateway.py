from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stores', '0006_store_plan_and_opening'),
    ]

    operations = [
        migrations.AddField(
            model_name='tienda',
            name='pasarela_activa',
            field=models.BooleanField(default=True),
        ),
    ]
