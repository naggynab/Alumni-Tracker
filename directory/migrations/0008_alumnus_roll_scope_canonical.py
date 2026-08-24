from django.db import migrations, models


def backfill_roll_scope_canonical(apps, schema_editor):
    from directory.choices import normalize_roll_scope

    Alumnus = apps.get_model("directory", "Alumnus")
    batch = []
    for alumnus in Alumnus.objects.only(
        "id", "class_roll_no", "field_of_study", "department_raw"
    ).iterator():
        alumnus.roll_scope_canonical = normalize_roll_scope(
            alumnus.class_roll_no,
            alumnus.field_of_study,
            alumnus.department_raw,
        )
        batch.append(alumnus)
        if len(batch) >= 1000:
            Alumnus.objects.bulk_update(batch, ["roll_scope_canonical"])
            batch = []
    if batch:
        Alumnus.objects.bulk_update(batch, ["roll_scope_canonical"])


class Migration(migrations.Migration):

    dependencies = [
        ("directory", "0007_alumnus_roll_number_canonical"),
    ]

    operations = [
        migrations.AddField(
            model_name="alumnus",
            name="roll_scope_canonical",
            field=models.CharField(blank=True, db_index=True, max_length=150),
        ),
        migrations.RunPython(backfill_roll_scope_canonical, migrations.RunPython.noop),
    ]
