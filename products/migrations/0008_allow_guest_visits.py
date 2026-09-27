from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0007_unique_product_visit_account'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='visitaproducto',
            name='unique_product_visit_account',
        ),
    ]
