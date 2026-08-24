from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("directory", "0011_alumniskill_communitygroup_skill_survey_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="alumnus",
            name="is_public",
            field=models.BooleanField(
                default=False,
                help_text="If on, the record appears in the public directory.",
            ),
        ),
    ]
