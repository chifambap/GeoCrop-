from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fields', '0011_fieldentry_prev_yield_tonnes'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='fieldentry',
            index=models.Index(
                fields=['survey'],
                name='fields_fiel_survey_idx',
            ),
        ),
        migrations.AddIndex(
            model_name='fieldentry',
            index=models.Index(
                fields=['updated_at'],
                name='fields_fiel_updated_idx',
            ),
        ),
    ]
