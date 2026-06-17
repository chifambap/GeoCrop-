from rest_framework import generics, permissions, status, filters
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from django.http import HttpResponse, FileResponse
from django.db.models import Count, Q
import json
import os
import shutil
import tempfile
import subprocess
import zipfile

from rest_framework import viewsets

from .models import FieldEntry, FieldPhoto, ValidationRecord, Survey
from .serializers import FieldEntrySerializer, ValidationSerializer, FieldPhotoSerializer, SurveySerializer


class IsCollectorOrAbove(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in (
            'admin', 'collector', 'validator'
        )


class IsValidatorOrAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in ('admin', 'validator')


# ─── Surveys ─────────────────────────────────────────────────────────────────

class SurveyViewSet(viewsets.ModelViewSet):
    serializer_class = SurveySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = Survey.objects.annotate(entry_count=Count('entries'))
        if self.request.user.role != 'admin':
            qs = qs.filter(is_active=True)
        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def create(self, request, *args, **kwargs):
        if request.user.role != 'admin':
            return Response({"detail": "Admin only"}, status=403)
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        if request.user.role != 'admin':
            return Response({"detail": "Admin only"}, status=403)
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        if request.user.role != 'admin':
            return Response({"detail": "Admin only"}, status=403)
        survey = self.get_object()
        if survey.entries.exists():
            return Response({"detail": "Cannot delete survey with entries"}, status=400)
        return super().destroy(request, *args, **kwargs)


# ─── Field Entries ────────────────────────────────────────────────────────────

class FieldEntryListCreateView(generics.ListCreateAPIView):
    serializer_class = FieldEntrySerializer
    permission_classes = [IsCollectorOrAbove]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['crop_type', 'season', 'growth_stage', 'irrigation', 'collected_by', 'survey']
    search_fields    = ['crop_type', 'notes']
    ordering_fields  = ['collected_at', 'crop_type']

    def get_queryset(self):
        qs = FieldEntry.objects.select_related('collected_by', 'validation') \
                               .prefetch_related('photos')
        # Non-admins only see their own entries
        if self.request.user.role not in ('admin', 'validator'):
            qs = qs.filter(collected_by=self.request.user)
        return qs

    def perform_create(self, serializer):
        serializer.save(collected_by=self.request.user)


class FieldEntryDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = FieldEntrySerializer
    permission_classes = [IsCollectorOrAbove]

    def get_queryset(self):
        qs = FieldEntry.objects.select_related('collected_by', 'validation') \
                               .prefetch_related('photos')
        if self.request.user.role not in ('admin', 'validator'):
            qs = qs.filter(collected_by=self.request.user)
        return qs


# ─── GeoJSON export ───────────────────────────────────────────────────────────

class FieldsGeoJSONView(APIView):
    """Return a proper FeatureCollection for map consumption."""
    permission_classes = [IsCollectorOrAbove]

    def get(self, request):
        from django.conf import settings
        qs = FieldEntry.objects.select_related('collected_by', 'validation') \
                               .prefetch_related('photos')
        if request.user.role not in ('admin', 'validator'):
            qs = qs.filter(collected_by=request.user)
        survey_id = request.query_params.get('survey')
        if survey_id:
            try:
                survey_id = int(survey_id)
            except (ValueError, TypeError):
                return HttpResponse('{"error":"Invalid survey id."}',
                                    content_type='application/json', status=400)
            qs = qs.filter(survey_id=survey_id)

        total_count = qs.count()
        cap = settings.GEOJSON_MAX_FEATURES
        truncated = total_count > cap
        qs = qs[:cap]  # slice before iteration; prefetch_related still works on sliced QS

        features = []
        for f in qs:
            if f.geom_polygon:
                geom = json.loads(f.geom_polygon.geojson)
            elif f.geom_point:
                geom = json.loads(f.geom_point.geojson)
            else:
                continue

            val = None
            try:
                v = f.validation
                val = {
                    'status':     v.status,
                    'confidence': v.confidence,
                    'note':       v.note,
                }
            except ValidationRecord.DoesNotExist:
                pass

            features.append({
                'type': 'Feature',
                'geometry': geom,
                'properties': {
                    'id':           f.pk,
                    'survey':       f.survey.name if f.survey else None,
                    'survey_id':    f.survey_id,
                    'crop_type':    f.crop_type,
                    'season':       f.season,
                    'growth_stage': f.growth_stage,
                    'irrigation':   f.irrigation,
                    'planting_date':str(f.planting_date) if f.planting_date else None,
                    'harvest_date': str(f.harvest_date)  if f.harvest_date  else None,
                    'notes':        f.notes,
                    'area_ha':      str(f.area_ha) if f.area_ha is not None else None,
                    'seed_used_kg': str(f.seed_used_kg) if f.seed_used_kg is not None else None,
                    'fertiliser_used_kg': str(f.fertiliser_used_kg) if f.fertiliser_used_kg is not None else None,
                    'yield_tonnes': str(f.yield_tonnes) if f.yield_tonnes is not None else None,
                    'prev_yield_tonnes': str(f.prev_yield_tonnes) if f.prev_yield_tonnes is not None else None,
                    'collected_by': f.collected_by.username if f.collected_by else None,
                    'collected_at': f.collected_at.isoformat(),
                    'validation':   val,
                    'photo_count':  len(f.photos.all()),  # uses prefetch cache — no extra query
                }
            })

        fc = {
            'type': 'FeatureCollection',
            'features': features,
            'truncated': truncated,
            'total_count': total_count,
        }
        return HttpResponse(json.dumps(fc), content_type='application/geo+json')


# ─── Photos ───────────────────────────────────────────────────────────────────

class FieldPhotoUploadView(APIView):
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [IsCollectorOrAbove]

    def post(self, request, pk):
        try:
            field = FieldEntry.objects.get(pk=pk)
        except FieldEntry.DoesNotExist:
            return Response({'detail': 'Field not found.'}, status=404)

        images = request.FILES.getlist('images')
        if not images:
            return Response({'detail': 'No images provided.'}, status=400)

        created = []
        for img in images:
            photo = FieldPhoto.objects.create(
                field=field, image=img,
                caption=request.data.get('caption', '')
            )
            created.append(FieldPhotoSerializer(photo, context={'request': request}).data)

        return Response(created, status=201)


# ─── Validation ───────────────────────────────────────────────────────────────

class ValidationCreateView(generics.CreateAPIView):
    serializer_class = ValidationSerializer
    permission_classes = [IsValidatorOrAdmin]

    def create(self, request, *args, **kwargs):
        pk = self.kwargs['pk']
        try:
            field = FieldEntry.objects.get(pk=pk)
        except FieldEntry.DoesNotExist:
            return Response({'detail': 'Field not found.'}, status=404)

        # Upsert — overwrite existing validation
        ValidationRecord.objects.filter(field=field).delete()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(field=field, validated_by=request.user)
        return Response(serializer.data, status=201)


# ─── Stats ────────────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def stats_view(request):
    qs = FieldEntry.objects.all()
    if request.user.role not in ('admin', 'validator'):
        qs = qs.filter(collected_by=request.user)
    survey_id = request.query_params.get('survey')
    if survey_id:
        try:
            survey_id = int(survey_id)
        except (ValueError, TypeError):
            return Response({'error': 'Invalid survey id.'}, status=400)
        qs = qs.filter(survey_id=survey_id)

    by_crop = list(qs.values('crop_type').annotate(count=Count('id')).order_by('-count'))
    validated = qs.filter(validation__isnull=False).count()

    return Response({
        'total':     qs.count(),
        'validated': validated,
        'polygons':  qs.filter(geom_polygon__isnull=False).count(),
        'points':    qs.filter(geom_point__isnull=False).count(),
        'by_crop':   by_crop,
        'validation_breakdown': {
            'correct':   qs.filter(validation__status='correct').count(),
            'incorrect': qs.filter(validation__status='incorrect').count(),
            'uncertain': qs.filter(validation__status='uncertain').count(),
        }
    })


# ─── Exports ──────────────────────────────────────────────────────────────────

class ExportFieldsView(APIView):
    permission_classes = []

    def _authenticate(self, request):
        from rest_framework_simplejwt.authentication import JWTAuthentication
        from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
        
        try:
            result = JWTAuthentication().authenticate(request)
            if result:
                return result[0]
        except (InvalidToken, TokenError):
            pass
            
        token_str = request.query_params.get('token')
        if token_str:
            try:
                from rest_framework_simplejwt.tokens import AccessToken
                from django.contrib.auth import get_user_model
                token = AccessToken(token_str)
                User = get_user_model()
                return User.objects.get(id=token['user_id'])
            except Exception:
                pass
        return None

    def get(self, request):
        user = self._authenticate(request)
        if not user:
            return HttpResponse('Unauthorized', status=401)

        # Use 'export_format' to avoid DRF's built-in ?format= content negotiation
        ALLOWED_FORMATS = {'geojson', 'gpkg', 'kml', 'shp'}
        fmt = request.query_params.get('export_format', 'geojson').lower()
        if fmt not in ALLOWED_FORMATS:
            return Response({'error': 'Invalid export_format. Use: geojson, gpkg, kml, shp'}, status=400)
        crop = request.query_params.get('crop_type', '')
        status_filter = request.query_params.get('status', '')

        # Filter queryset
        qs = FieldEntry.objects.all()
        survey_id = request.query_params.get('survey')
        if survey_id:
            try:
                survey_id = int(survey_id)
            except (ValueError, TypeError):
                return Response({'error': 'Invalid survey id.'}, status=400)
            qs = qs.filter(survey_id=survey_id)
        if crop:
            qs = qs.filter(crop_type=crop)
        if status_filter == 'none':
            qs = qs.filter(validation__isnull=True)
        elif status_filter:
            qs = qs.filter(validation__status=status_filter)

        # Adaptive row cap — prevents RAM exhaustion on large datasets
        from django.conf import settings
        qs = qs.select_related('collected_by', 'validation')
        total_count = qs.count()
        cap = settings.EXPORT_MAX_ROWS
        truncated = total_count > cap

        # Build GeoJSON — iterator() is safe here (no prefetch_related)
        features = []
        for entry in qs[:cap].iterator(chunk_size=settings.ITERATOR_CHUNK_SIZE):
            # Build geometry from geom_polygon or geom_point
            geom = entry.geom_polygon or entry.geom_point
            if not geom:
                continue
            geom_json = json.loads(geom.geojson)

            props = {
                'id': entry.id,
                'survey': entry.survey.name if entry.survey else None,
                'crop_type': entry.crop_type,
                'sector': entry.sector,
                'season': entry.season,
                'growth_stage': entry.growth_stage,
                'crop_condition': entry.crop_condition,
                'irrigation': entry.irrigation,
                'planting_date': str(entry.planting_date) if entry.planting_date else None,
                'area_ha': str(entry.area_ha) if entry.area_ha is not None else None,
                'seed_used_kg': str(entry.seed_used_kg) if entry.seed_used_kg is not None else None,
                'fertiliser_used_kg': str(entry.fertiliser_used_kg) if entry.fertiliser_used_kg is not None else None,
                'yield_tonnes': str(entry.yield_tonnes) if entry.yield_tonnes is not None else None,
                'prev_yield_tonnes': str(entry.prev_yield_tonnes) if entry.prev_yield_tonnes is not None else None,
                'collected_by': entry.collected_by.username if entry.collected_by else None,
                'collected_at': entry.collected_at.isoformat() if entry.collected_at else None,
            }
            try:
                props['validation_status'] = entry.validation.status
                props['validation_confidence'] = entry.validation.confidence
            except ValidationRecord.DoesNotExist:
                pass

            features.append({
                'type': 'Feature',
                'geometry': geom_json,
                'properties': props
            })

        geojson_data = {
            'type': 'FeatureCollection',
            'features': features,
            'truncated': truncated,
            'total_count': total_count,
        }

        if fmt == 'geojson':
            content = json.dumps(geojson_data)
            return HttpResponse(content, content_type='application/geo+json', headers={
                'Content-Disposition': 'attachment; filename="geocrop_export.geojson"'
            })

        # For GDAL formats, write GeoJSON to temp file then use ogr2ogr
        fd, temp_json = tempfile.mkstemp(suffix='.geojson')
        out_file = out_dir = zip_path = None
        with os.fdopen(fd, 'w') as f:
            json.dump(geojson_data, f)

        try:
            if fmt == 'gpkg':
                out_file = temp_json.replace('.geojson', '.gpkg')
                subprocess.run(['ogr2ogr', '-f', 'GPKG', out_file, temp_json], check=True)
                data = open(out_file, 'rb').read()
                return HttpResponse(data, content_type='application/geopackage+sqlite3', headers={
                    'Content-Disposition': 'attachment; filename="geocrop_export.gpkg"'
                })

            elif fmt == 'kml':
                out_file = temp_json.replace('.geojson', '.kml')
                subprocess.run(['ogr2ogr', '-f', 'KML', out_file, temp_json], check=True)
                data = open(out_file, 'rb').read()
                return HttpResponse(data, content_type='application/vnd.google-earth.kml+xml', headers={
                    'Content-Disposition': 'attachment; filename="geocrop_export.kml"'
                })

            elif fmt == 'shp':
                out_dir  = tempfile.mkdtemp()
                zip_path = temp_json.replace('.geojson', '.zip')

                # Split features by geometry type (Shapefiles only support one type per file)
                points = [f for f in features if f['geometry']['type'] == 'Point']
                polys  = [f for f in features if f['geometry']['type'] in ('Polygon', 'MultiPolygon')]

                shp_files_created = False
                for label, subset in [('points', points), ('polygons', polys)]:
                    if not subset:
                        continue
                    fc_subset = {'type': 'FeatureCollection', 'features': subset}
                    fd2, tmp2 = tempfile.mkstemp(suffix='.geojson')
                    try:
                        with os.fdopen(fd2, 'w') as f2:
                            json.dump(fc_subset, f2)
                        out_shp = os.path.join(out_dir, f'geocrop_{label}.shp')
                        subprocess.run(['ogr2ogr', '-f', 'ESRI Shapefile', out_shp, tmp2], check=True)
                        shp_files_created = True
                    finally:
                        if os.path.exists(tmp2):
                            os.unlink(tmp2)

                if not shp_files_created:
                    return Response({"error": "No exportable features"}, status=400)

                # Zip all shapefile components
                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                    for root, _, files in os.walk(out_dir):
                        for file in files:
                            zf.write(os.path.join(root, file), file)
                data = open(zip_path, 'rb').read()
                return HttpResponse(data, content_type='application/zip', headers={
                    'Content-Disposition': 'attachment; filename="geocrop_shp.zip"'
                })

            else:
                return Response({"error": "Unsupported export_format"}, status=400)

        except subprocess.CalledProcessError as e:
            return Response({"error": f"Export failed: {e}"}, status=500)

        finally:
            if temp_json and os.path.exists(temp_json):
                os.unlink(temp_json)
            if out_file and os.path.exists(out_file):
                os.unlink(out_file)
            if zip_path and os.path.exists(zip_path):
                os.unlink(zip_path)
            if out_dir and os.path.exists(out_dir):
                shutil.rmtree(out_dir, ignore_errors=True)

