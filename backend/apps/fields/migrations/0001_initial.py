# Generated initial migration for fields app

from django.conf import settings
import django.contrib.gis.db.models.fields
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='FieldEntry',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('geom_polygon', django.contrib.gis.db.models.fields.PolygonField(blank=True, null=True, srid=4326)),
                ('geom_point', django.contrib.gis.db.models.fields.PointField(blank=True, null=True, srid=4326)),
                ('collected_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('device_id', models.CharField(blank=True, max_length=64)),
                ('client_uuid', models.UUIDField(blank=True, null=True, unique=True)),
                ('crop_type', models.CharField(choices=[('wheat', 'Wheat'), ('maize', 'Maize / Corn'), ('rice', 'Rice'), ('soybean', 'Soybean'), ('sorghum', 'Sorghum'), ('tobacco', 'Tobacco'), ('sunflower', 'Sunflower'), ('cotton', 'Cotton'), ('sugarcane', 'Sugarcane'), ('potato', 'Potato'), ('barley', 'Barley'), ('millet', 'Millet'), ('groundnut', 'Groundnut'), ('cassava', 'Cassava'), ('fallow', 'Fallow / Bare'), ('other', 'Other')], max_length=20)),
                ('season', models.CharField(blank=True, choices=[('main', 'Main Season'), ('secondary', 'Secondary Season'), ('irrigated', 'Irrigated (Off-season)')], max_length=20)),
                ('growth_stage', models.CharField(blank=True, choices=[('land-prep', 'Land Preparation'), ('seedling', 'Seedling / Emergence'), ('vegetative', 'Vegetative'), ('flowering', 'Flowering / Heading'), ('grain-fill', 'Grain Filling / Maturity'), ('harvest-ready', 'Harvest Ready'), ('post-harvest', 'Post Harvest')], max_length=20)),
                ('irrigation', models.CharField(blank=True, choices=[('rainfed', 'Rainfed'), ('irrigated', 'Irrigated'), ('unknown', 'Unknown')], max_length=20)),
                ('planting_date', models.DateField(blank=True, null=True)),
                ('harvest_date', models.DateField(blank=True, null=True)),
                ('notes', models.TextField(blank=True)),
                ('collected_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='fields_collected', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-collected_at'],
            },
        ),
        migrations.CreateModel(
            name='ValidationRecord',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('validated_at', models.DateTimeField(auto_now_add=True)),
                ('status', models.CharField(choices=[('correct', 'Correct'), ('incorrect', 'Incorrect'), ('uncertain', 'Uncertain')], max_length=20)),
                ('confidence', models.PositiveSmallIntegerField()),
                ('note', models.TextField(blank=True)),
                ('field', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='validation', to='fields.fieldentry')),
                ('validated_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='validations_done', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-validated_at'],
            },
        ),
        migrations.CreateModel(
            name='FieldPhoto',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('image', models.ImageField(upload_to='field_photos/%Y/%m/')),
                ('caption', models.CharField(blank=True, max_length=255)),
                ('taken_at', models.DateTimeField(blank=True, null=True)),
                ('uploaded_at', models.DateTimeField(auto_now_add=True)),
                ('field', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='photos', to='fields.fieldentry')),
            ],
        ),
        migrations.AddIndex(
            model_name='fieldentry',
            index=models.Index(fields=['crop_type'], name='fields_fiel_crop_ty_8e3c6e_idx'),
        ),
        migrations.AddIndex(
            model_name='fieldentry',
            index=models.Index(fields=['collected_by'], name='fields_fiel_collect_3a5b0d_idx'),
        ),
        migrations.AddIndex(
            model_name='fieldentry',
            index=models.Index(fields=['collected_at'], name='fields_fiel_collect_2e4a3f_idx'),
        ),
        migrations.AddIndex(
            model_name='fieldentry',
            index=models.Index(fields=['client_uuid'], name='fields_fiel_client__7f8e2a_idx'),
        ),
    ]
