from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('stores', '0004_unique_store_visit_account'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='visitatienda',
            name='unique_store_visit_account',
        ),
    ]
