from rest_framework import serializers
from rest_framework_gis.serializers import GeoFeatureModelSerializer
from .models import FieldEntry, FieldPhoto, ValidationRecord, Survey


class FieldPhotoSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model  = FieldPhoto
        fields = ['id', 'image_url', 'caption', 'taken_at', 'uploaded_at']

    def get_image_url(self, obj):
        request = self.context.get('request')
        if request and obj.image:
            return request.build_absolute_uri(obj.image.url)
        return None


class ValidationSerializer(serializers.ModelSerializer):
    validated_by_name = serializers.CharField(source='validated_by.username', read_only=True)

    class Meta:
        model  = ValidationRecord
        fields = ['id', 'status', 'confidence', 'note', 'validated_by_name', 'validated_at']
        read_only_fields = ['id', 'validated_by_name', 'validated_at']


class SurveySerializer(serializers.ModelSerializer):
    entry_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model  = Survey
        fields = ['id', 'name', 'is_active', 'entry_count', 'created_at']
        read_only_fields = ['id', 'created_at']


class FieldEntrySerializer(serializers.ModelSerializer):
    photos            = FieldPhotoSerializer(many=True, read_only=True)
    validation        = ValidationSerializer(read_only=True)
    collected_by_name = serializers.CharField(source='collected_by.username', read_only=True)
    geometry_type     = serializers.ReadOnlyField()

    # Accept GeoJSON geometry on write
    geometry = serializers.JSONField(write_only=True, required=True)
    # Accept free-text sector (e.g. custom "Other" values)
    sector   = serializers.CharField(max_length=100, required=False, allow_blank=True)

    class Meta:
        model  = FieldEntry
        fields = [
            'id', 'geometry_type', 'geometry',
            'survey',
            'sector', 'crop_type', 'season', 'growth_stage', 'crop_condition', 'irrigation',
            'planting_date', 'harvest_date', 'notes',
            'area_ha', 'seed_used_kg', 'fertiliser_used_kg', 'yield_tonnes', 'prev_yield_tonnes',
            'collected_by', 'collected_by_name', 'collected_at', 'updated_at',
            'device_id', 'client_uuid',
            'photos', 'validation',
        ]
        read_only_fields = ['id', 'collected_by', 'collected_at', 'updated_at']

    def validate_geometry(self, value):
        from django.contrib.gis.geos import GEOSGeometry
        import json
        try:
            geom = GEOSGeometry(json.dumps(value))
        except Exception:
            raise serializers.ValidationError('Invalid GeoJSON geometry.')
        if geom.geom_type not in ('Point', 'Polygon'):
            raise serializers.ValidationError('Only Point or Polygon geometries are supported.')
        if geom.srid != 4326:
            geom.transform(4326)
        return value

    def create(self, validated_data):
        from django.contrib.gis.geos import GEOSGeometry
        import json
        geometry = validated_data.pop('geometry')
        geom = GEOSGeometry(json.dumps(geometry))
        instance = FieldEntry(**validated_data)
        instance.collected_by = self.context['request'].user
        if geom.geom_type == 'Point':
            instance.geom_point = geom
        else:
            instance.geom_polygon = geom
        instance.save()
        return instance

    def update(self, instance, validated_data):
        from django.contrib.gis.geos import GEOSGeometry
        import json
        if 'geometry' in validated_data:
            geometry = validated_data.pop('geometry')
            geom = GEOSGeometry(json.dumps(geometry))
            if geom.geom_type == 'Point':
                instance.geom_point   = geom
                instance.geom_polygon = None
            else:
                instance.geom_polygon = geom
                instance.geom_point   = None
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class FieldEntryGeoJSONSerializer(GeoFeatureModelSerializer):
    """Returns FeatureCollection GeoJSON for map display."""
    photos     = FieldPhotoSerializer(many=True, read_only=True)
    validation = ValidationSerializer(read_only=True)

    class Meta:
        model  = FieldEntry
        geo_field = 'geom_polygon'    # override in get_queryset if needed
        fields = [
            'id', 'crop_type', 'season', 'growth_stage', 'irrigation',
            'planting_date', 'harvest_date', 'notes',
            'collected_by', 'collected_at', 'photos', 'validation',
        ]
