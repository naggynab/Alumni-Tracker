from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("directory", "0002_alumnus_further_study_degree"),
    ]

    operations = [
        migrations.AlterField(
            model_name="alumnus",
            name="class_roll_no",
            field=models.CharField(blank=True, db_index=True, max_length=30),
        ),
    ]
