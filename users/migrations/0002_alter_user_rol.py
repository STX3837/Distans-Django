from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='rol',
            field=models.CharField(choices=[('comprador', 'Comprador'), ('vendedor', 'Vendedor'), ('admin', 'Admin')], default='comprador', max_length=20),
        ),
    ]