from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('stores', '0008_make_store_creation_date_required')]
    operations = [
        migrations.AddField(model_name='tienda', name='stripe_subscription_id', field=models.CharField(max_length=255, null=True, blank=True, unique=True)),
        migrations.AddField(model_name='tienda', name='premium_hasta', field=models.DateTimeField(null=True, blank=True)),
        migrations.AddField(model_name='tienda', name='stripe_premium_checkout_id', field=models.CharField(max_length=255, blank=True, default='')),
    ]
