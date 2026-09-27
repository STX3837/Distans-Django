from django.db import migrations, models


def remove_duplicate_visits(apps, schema_editor):
    visita_model = apps.get_model('stores', 'VisitaTienda')
    seen = set()
    duplicate_ids = []
    for visita in visita_model.objects.order_by('tienda_id', 'session_key', 'id'):
        key = (visita.tienda_id, visita.session_key)
        if key in seen:
            duplicate_ids.append(visita.id)
        else:
            seen.add(key)
    if duplicate_ids:
        visita_model.objects.filter(id__in=duplicate_ids).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('stores', '0003_store_visit'),
    ]

    operations = [
        migrations.RunPython(remove_duplicate_visits, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='visitatienda',
            constraint=models.UniqueConstraint(
                fields=('tienda', 'session_key'),
                name='unique_store_visit_account',
            ),
        ),
    ]
