from django.db import migrations, models
import django.db.models.deletion
from django_countries.fields import CountryField


def copy_existing_further_study(apps, schema_editor):
    Alumnus = apps.get_model("directory", "Alumnus")
    FurtherStudy = apps.get_model("directory", "FurtherStudy")

    for alumnus in Alumnus.objects.exclude(
        further_study_institution="",
        further_study_degree="",
        further_study_country="",
    ):
        FurtherStudy.objects.create(
            alumnus_id=alumnus.pk,
            degree_level="master",
            institution=alumnus.further_study_institution,
            degree=alumnus.further_study_degree,
            country=str(alumnus.further_study_country or ""),
        )


class Migration(migrations.Migration):
    dependencies = [
        ("directory", "0014_servicerequestreply"),
    ]

    operations = [
        migrations.CreateModel(
            name="FurtherStudy",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "degree_level",
                    models.CharField(
                        choices=[
                            ("bachelor", "Bachelor"),
                            ("master", "Master"),
                            ("phd", "PhD"),
                        ],
                        max_length=15,
                    ),
                ),
                ("institution", models.CharField(blank=True, max_length=150)),
                ("degree", models.CharField(blank=True, max_length=100)),
                ("country", CountryField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "alumnus",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="further_studies",
                        to="directory.alumnus",
                    ),
                ),
            ],
            options={"ordering": ["degree_level", "created_at", "pk"]},
        ),
        migrations.RunPython(copy_existing_further_study, migrations.RunPython.noop),
    ]
