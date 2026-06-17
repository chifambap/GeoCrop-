from django.db import models
from django.conf import settings
import os


def mbtiles_upload_path(instance, filename):
    return f'mbtiles/{instance.uploaded_by.username}/{filename}'


class MBTilesFile(models.Model):
    """An uploaded georeferenced MBTiles file."""

    name        = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    file        = models.FileField(upload_to=mbtiles_upload_path)
    file_size   = models.BigIntegerField(default=0)  # bytes
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='mbtiles_uploads'
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    is_active   = models.BooleanField(default=True)

    # Bounding box metadata (extracted from MBTiles)
    min_zoom  = models.IntegerField(default=0)
    max_zoom  = models.IntegerField(default=18)
    bounds    = models.CharField(max_length=100, blank=True)  # "minLng,minLat,maxLng,maxLat"
    center    = models.CharField(max_length=60, blank=True)   # "lng,lat,zoom"

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return self.name

    @property
    def file_size_mb(self):
        return round(self.file_size / (1024 * 1024), 2)

    def save(self, *args, **kwargs):
        if self.file and hasattr(self.file, 'size'):
            self.file_size = self.file.size
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Remove the physical file on delete."""
        path = self.file.path if self.file else None
        super().delete(*args, **kwargs)
        if path and os.path.exists(path):
            os.remove(path)


def overlay_upload_path(instance, filename):
    return f'overlays/{instance.uploaded_by.username}/{filename}'


class RouteOverlay(models.Model):
    """An uploaded vector overlay file (GeoJSON, GPKG, KML) for navigation/route display."""

    name           = models.CharField(max_length=255)
    description    = models.TextField(blank=True)
    original_file  = models.FileField(upload_to=overlay_upload_path)
    geojson_file   = models.FileField(upload_to='overlays/geojson/', blank=True)
    file_format    = models.CharField(max_length=10)  # 'geojson', 'gpkg', 'kml'
    file_size      = models.BigIntegerField(default=0)
    feature_count  = models.IntegerField(default=0)
    bounds         = models.CharField(max_length=100, blank=True)  # "minLng,minLat,maxLng,maxLat"
    uploaded_by    = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='overlay_uploads'
    )
    uploaded_at    = models.DateTimeField(auto_now_add=True)
    is_active      = models.BooleanField(default=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return self.name

    @property
    def file_size_mb(self):
        return round(self.file_size / (1024 * 1024), 2)

    def delete(self, *args, **kwargs):
        orig = self.original_file.path if self.original_file else None
        geo = self.geojson_file.path if self.geojson_file else None
        super().delete(*args, **kwargs)
        for p in [orig, geo]:
            if p and os.path.exists(p):
                os.remove(p)
