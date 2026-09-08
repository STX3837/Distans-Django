from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0008_allow_guest_visits'),
        ('stores', '0005_allow_guest_visits'),
        ('users', '0002_alter_user_rol'),
    ]

    operations = [
        migrations.CreateModel(
            name='Favorite',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('producto', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='favoritos', to='products.producto')),
                ('tienda', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='favoritos', to='stores.tienda')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('usuario', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='favoritos', to='users.user')),
            ],
            options={
                'constraints': [
                    models.UniqueConstraint(fields=('usuario', 'producto'), name='unique_user_product_favorite'),
                    models.UniqueConstraint(fields=('usuario', 'tienda'), name='unique_user_store_favorite'),
                    models.CheckConstraint(check=models.Q(('producto__isnull', False), ('tienda__isnull', True)) | models.Q(('producto__isnull', True), ('tienda__isnull', False)), name='favorite_has_one_target'),
                ],
            },
        ),
    ]