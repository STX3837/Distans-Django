from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stores', '0007_store_payment_gateway'),
    ]

    operations = [
        migrations.AlterField(
            model_name='tienda',
            name='fecha_alta',
            field=models.DateField(auto_now_add=True),
        ),
    ]