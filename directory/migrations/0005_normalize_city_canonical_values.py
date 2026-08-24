from django.db import migrations


def backfill_city_canonical(apps, schema_editor):
    from directory.choices import normalize_city

    Alumnus = apps.get_model("directory", "Alumnus")
    updates = []
    for alumnus in Alumnus.objects.all().only("id", "current_city").iterator(chunk_size=500):
        alumnus.current_city_canonical = normalize_city(alumnus.current_city)
        updates.append(alumnus)
        if len(updates) >= 500:
            Alumnus.objects.bulk_update(updates, ["current_city_canonical"])
            updates = []
    if updates:
        Alumnus.objects.bulk_update(updates, ["current_city_canonical"])


class Migration(migrations.Migration):
    dependencies = [("directory", "0004_alumnus_canonical_fields")]

    operations = [migrations.RunPython(backfill_city_canonical, migrations.RunPython.noop)]
