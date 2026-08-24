from django.db import migrations, models


def backfill_roll_number_canonical(apps, schema_editor):
    from directory.choices import normalize_roll_serial

    Alumnus = apps.get_model("directory", "Alumnus")
    batch = []
    for alumnus in Alumnus.objects.only("id", "class_roll_no").iterator():
        alumnus.roll_number_canonical = normalize_roll_serial(alumnus.class_roll_no)
        batch.append(alumnus)
        if len(batch) >= 1000:
            Alumnus.objects.bulk_update(batch, ["roll_number_canonical"])
            batch = []
    if batch:
        Alumnus.objects.bulk_update(batch, ["roll_number_canonical"])


class Migration(migrations.Migration):

    dependencies = [
        ("directory", "0006_followup_claimreview"),
    ]

    operations = [
        migrations.AddField(
            model_name="alumnus",
            name="roll_number_canonical",
            field=models.CharField(blank=True, db_index=True, max_length=30),
        ),
        migrations.RunPython(backfill_roll_number_canonical, migrations.RunPython.noop),
    ]
