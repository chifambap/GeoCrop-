from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fields', '0010_fieldentry_area_ha_fieldentry_fertiliser_used_kg_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='fieldentry',
            name='prev_yield_tonnes',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
    ]
