from django.db import migrations, models


def backfill_canonical_fields(apps, schema_editor):
    from directory.choices import normalize_city, normalize_employer, normalize_institution

    Alumnus = apps.get_model("directory", "Alumnus")
    updates = []
    for alumnus in Alumnus.objects.all().only(
        "id", "current_city", "employer_organization", "further_study_institution"
    ).iterator(chunk_size=500):
        alumnus.current_city_canonical = normalize_city(alumnus.current_city)
        alumnus.employer_canonical = normalize_employer(alumnus.employer_organization)
        alumnus.further_study_institution_canonical = normalize_institution(
            alumnus.further_study_institution
        )
        updates.append(alumnus)
        if len(updates) >= 500:
            Alumnus.objects.bulk_update(
                updates,
                [
                    "current_city_canonical",
                    "employer_canonical",
                    "further_study_institution_canonical",
                ],
            )
            updates = []
    if updates:
        Alumnus.objects.bulk_update(
            updates,
            [
                "current_city_canonical",
                "employer_canonical",
                "further_study_institution_canonical",
            ],
        )


class Migration(migrations.Migration):
    dependencies = [("directory", "0003_alumnus_class_roll_no_index")]

    operations = [
        migrations.AddField(
            model_name="alumnus",
            name="current_city_canonical",
            field=models.CharField(blank=True, db_index=True, max_length=100),
        ),
        migrations.AddField(
            model_name="alumnus",
            name="employer_canonical",
            field=models.CharField(blank=True, db_index=True, max_length=150),
        ),
        migrations.AddField(
            model_name="alumnus",
            name="further_study_institution_canonical",
            field=models.CharField(blank=True, db_index=True, max_length=150),
        ),
        migrations.RunPython(backfill_canonical_fields, migrations.RunPython.noop),
    ]
