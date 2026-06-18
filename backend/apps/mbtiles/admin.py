from django.contrib import admin
from .models import MBTilesFile

@admin.register(MBTilesFile)
class MBTilesAdmin(admin.ModelAdmin):
    list_display  = ['name', 'file_size_mb', 'min_zoom', 'max_zoom', 'uploaded_by', 'uploaded_at', 'is_active']
    list_filter   = ['is_active']
    search_fields = ['name', 'description']
    readonly_fields = ['file_size', 'uploaded_at', 'min_zoom', 'max_zoom', 'bounds', 'center']
