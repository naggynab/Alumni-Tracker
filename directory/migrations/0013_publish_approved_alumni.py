from django.db import migrations, models


def publish_approved_alumni(apps, schema_editor):
    Alumnus = apps.get_model("directory", "Alumnus")
    Alumnus.objects.all().update(is_public=True)


def unpublish_alumni(apps, schema_editor):
    Alumnus = apps.get_model("directory", "Alumnus")
    Alumnus.objects.all().update(is_public=False)


class Migration(migrations.Migration):
    dependencies = [
        ("directory", "0012_alumnus_private_by_default"),
    ]

    operations = [
        migrations.AlterField(
            model_name="alumnus",
            name="is_public",
            field=models.BooleanField(
                default=True,
                help_text="If on, the record appears in the public directory.",
            ),
        ),
        migrations.RunPython(publish_approved_alumni, unpublish_alumni),
    ]
