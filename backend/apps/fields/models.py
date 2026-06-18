from django.contrib.gis.db import models as gis_models
from django.db import models
from django.conf import settings


class CropType(models.TextChoices):
    MAIZE            = 'maize',            'Maize'
    TOBACCO          = 'tobacco',          'Tobacco'
    SESAME           = 'sesame',           'Sesame'
    SORGHUM          = 'sorghum',          'Sorghum'
    COTTON           = 'cotton',           'Cotton'
    PEARL_MILLET     = 'pearl_millet',     'Pearl Millet'
    GROUNDNUT        = 'groundnut',        'Groundnut'
    SOYABEAN         = 'soyabean',         'Soyabean'
    FINGER_MILLET    = 'finger_millet',    'Finger millet'
    POTATO           = 'potato',           'Potato'
    SUNFLOWER        = 'sunflower',        'Sunflower'
    TEA              = 'tea',              'Tea'
    PEPPER           = 'pepper',           'Pepper'
    ROUNDNUT         = 'roundnut',         'Roundnut'
    SUGARCANE        = 'sugarcane',        'Sugarcane'
    CABBAGE          = 'cabbage',          'Cabbage'
    BANANA           = 'banana',           'Banana'
    TOMATO           = 'tomato',           'Tomato'
    SUGARBEAN        = 'sugarbean',        'Sugarbean'
    MACADEMIA        = 'macademia',        'Macademia'
    BAMBARANUTS      = 'bambaranuts',      'Bambaranuts'
    COWPEA           = 'cowpea',           'African Pea/Cowpea'
    PAPRIKA          = 'paprika',          'Paprika'
    RICE             = 'rice',             'Rice'
    CASSAVA          = 'cassava',          'Cassava'
    CHICK_PEA        = 'chick_pea',        'Chick Pea'
    PIGEON_PEA       = 'pigeon_pea',       'Pigeon Pea'
    SUMMER_WHEAT     = 'summer_wheat',     'Summer Wheat'
    CASTER_BEANS     = 'caster_beans',     'Caster Beans'
    COCOYAM          = 'cocoyam',          'Cocoyam'
    TSENZA           = 'tsenza',           'Tsenza'
    WHEAT            = 'wheat',            'Wheat'
    BARLEY           = 'barley',           'Barley'
    PEA              = 'pea',              'Pea'
    OTHER            = 'other',            'Other crop'


class Season(models.TextChoices):
    MAIN       = 'main',      'Main Season'
    SECONDARY  = 'secondary', 'Secondary Season'
    IRRIGATED  = 'irrigated', 'Irrigated (Off-season)'


class GrowthStage(models.TextChoices):
    EMERGENCE      = 'emergence',         'Emergence'
    EARLY_VEG      = 'early_vegetative',  'Early Vegetative'
    LATE_VEG       = 'late_vegetative',   'Late Vegetative'
    EARLY_PROD     = 'early_productive',  'Early Productive'
    LATE_REPROD    = 'late_reproductive', 'Late Reproductive'
    MATURITY       = 'maturity',          'Maturity'
    SENESCENCE     = 'senescence',        'Senescence'
    HARVESTED      = 'harvested',         'Harvested'


class Irrigation(models.TextChoices):
    RAINFED   = 'rainfed',  'Rainfed'
    IRRIGATED = 'irrigated','Irrigated'
    UNKNOWN   = 'unknown',  'Unknown'


class CropCondition(models.TextChoices):
    PERMANENT_WILTING   = 'permanent_wilting',    'Permanent Wilting'
    TEMPORARY_WILTING   = 'temporary_wilting',    'Temporary Wilting'
    POOR                = 'poor',                 'Poor'
    FAIR                = 'fair',                 'Fair'
    GOOD                = 'good',                 'Good'
    LEACHED_WATERLOGGED = 'leached_waterlogged',  'Leeached/Waterlogged'

class Sector(models.TextChoices):
    LSCFA       = 'lscfa',       'LSCFA'
    A2          = 'a2',          'A2'
    A1          = 'a1',          'A1'
    SSCFA       = 'sscfa',       'SSCFA'
    OR          = 'or',          'OR'
    CA          = 'ca',          'CA'
    PERI_URBAN  = 'peri_urban',  'Peri urban'
    OTHER       = 'other',       'Other'


class Survey(models.Model):
    """A named survey/campaign that groups field entries."""
    name       = models.CharField(max_length=200, unique=True)
    is_active  = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class FieldEntry(gis_models.Model):
    """A collected crop field — either a polygon or a point."""

    # Geometry: nullable so we can store both poly and point separately
    geom_polygon = gis_models.PolygonField(srid=4326, null=True, blank=True)
    geom_point   = gis_models.PointField(srid=4326, null=True, blank=True)

    # Survey
    survey = models.ForeignKey(Survey, on_delete=models.SET_NULL, null=True, blank=True, related_name='entries')

    # Who & when
    collected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='fields_collected'
    )
    collected_at = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    # Device sync key (UUID generated on device, prevents duplicate uploads)
    device_id    = models.CharField(max_length=64, blank=True)
    client_uuid  = models.UUIDField(null=True, blank=True, unique=True)

    # Crop attributes
    sector       = models.CharField(max_length=100, blank=True)
    crop_type    = models.CharField(max_length=20, choices=CropType.choices)
    season       = models.CharField(max_length=20, choices=Season.choices, blank=True)
    growth_stage = models.CharField(max_length=20, choices=GrowthStage.choices, blank=True)
    crop_condition = models.CharField(max_length=50, choices=CropCondition.choices, blank=True)
    irrigation   = models.CharField(max_length=20, choices=Irrigation.choices, blank=True)
    planting_date = models.DateField(null=True, blank=True)
    harvest_date  = models.DateField(null=True, blank=True)
    notes        = models.TextField(blank=True)
    area_ha            = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    seed_used_kg       = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    fertiliser_used_kg = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    yield_tonnes      = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    prev_yield_tonnes = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    class Meta:
        ordering = ['-collected_at']
        indexes  = [
            models.Index(fields=['crop_type']),
            models.Index(fields=['collected_by']),
            models.Index(fields=['collected_at']),
            models.Index(fields=['client_uuid']),
        ]

    def __str__(self):
        return f'{self.crop_type} by {self.collected_by} at {self.collected_at:%Y-%m-%d}'

    @property
    def geometry_type(self):
        if self.geom_polygon:
            return 'Polygon'
        if self.geom_point:
            return 'Point'
        return None


def photo_upload_path(instance, filename):
    return f'field_photos/{instance.field.collected_at:%Y/%m}/{instance.field.pk}/{filename}'


class FieldPhoto(models.Model):
    """Attached photo evidence for a field entry."""
    field     = models.ForeignKey(FieldEntry, on_delete=models.CASCADE, related_name='photos')
    image     = models.ImageField(upload_to=photo_upload_path)
    caption   = models.CharField(max_length=255, blank=True)
    taken_at  = models.DateTimeField(null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Photo for field {self.field_id}'


class ValidationRecord(models.Model):
    """Validation review attached to a FieldEntry."""

    class Status(models.TextChoices):
        CORRECT   = 'correct',   'Correct'
        INCORRECT = 'incorrect', 'Incorrect'
        UNCERTAIN = 'uncertain', 'Uncertain'

    field        = models.OneToOneField(FieldEntry, on_delete=models.CASCADE, related_name='validation')
    validated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='validations_done'
    )
    validated_at = models.DateTimeField(auto_now_add=True)
    status       = models.CharField(max_length=20, choices=Status.choices)
    confidence   = models.PositiveSmallIntegerField()   # 1–5
    note         = models.TextField(blank=True)

    class Meta:
        ordering = ['-validated_at']

    def __str__(self):
        return f'Validation({self.status}) for field {self.field_id}'
