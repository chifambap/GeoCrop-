from django.contrib import admin
from django.contrib.gis.admin import GISModelAdmin
from .models import FieldEntry, FieldPhoto, ValidationRecord


class FieldPhotoInline(admin.TabularInline):
    model  = FieldPhoto
    extra  = 0
    readonly_fields = ['uploaded_at']


class ValidationInline(admin.StackedInline):
    model  = ValidationRecord
    extra  = 0
    readonly_fields = ['validated_at']


@admin.register(FieldEntry)
class FieldEntryAdmin(GISModelAdmin):
    list_display  = ['id', 'crop_type', 'season', 'growth_stage',
                     'collected_by', 'collected_at', 'has_validation']
    list_filter   = ['crop_type', 'season', 'growth_stage', 'irrigation']
    search_fields = ['crop_type', 'notes', 'collected_by__username']
    readonly_fields = ['collected_at', 'updated_at']
    inlines       = [FieldPhotoInline, ValidationInline]

    def has_validation(self, obj):
        return hasattr(obj, 'validation')
    has_validation.boolean = True
    has_validation.short_description = 'Validated'


@admin.register(ValidationRecord)
class ValidationAdmin(admin.ModelAdmin):
    list_display = ['field', 'status', 'confidence', 'validated_by', 'validated_at']
    list_filter  = ['status', 'confidence']
