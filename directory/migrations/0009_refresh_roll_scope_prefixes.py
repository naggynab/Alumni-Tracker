from django.db import migrations


def refresh_roll_scope_prefixes(apps, schema_editor):
    from directory.choices import normalize_roll_scope

    Alumnus = apps.get_model("directory", "Alumnus")
    batch = []
    for alumnus in Alumnus.objects.only(
        "id", "class_roll_no", "field_of_study", "department_raw"
    ).iterator():
        value = normalize_roll_scope(
            alumnus.class_roll_no,
            alumnus.field_of_study,
            alumnus.department_raw,
        )
        if alumnus.roll_scope_canonical != value:
            alumnus.roll_scope_canonical = value
            batch.append(alumnus)
        if len(batch) >= 1000:
            Alumnus.objects.bulk_update(batch, ["roll_scope_canonical"])
            batch = []
    if batch:
        Alumnus.objects.bulk_update(batch, ["roll_scope_canonical"])


class Migration(migrations.Migration):

    dependencies = [
        ("directory", "0008_alumnus_roll_scope_canonical"),
    ]

    operations = [
        migrations.RunPython(refresh_roll_scope_prefixes, migrations.RunPython.noop),
    ]
