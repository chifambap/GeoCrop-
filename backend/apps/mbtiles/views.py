import json
import os
import shutil
import sqlite3
import subprocess
import tempfile
from functools import lru_cache

from django.conf import settings
from django.core.exceptions import SuspiciousOperation, RequestDataTooBig
from django.http import FileResponse, HttpResponse, Http404
from rest_framework import generics, permissions, status
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import serializers

from .models import MBTilesFile, RouteOverlay


# ─── Serializer ──────────────────────────────────────────────────────────────

class MBTilesSerializer(serializers.ModelSerializer):
    file_size_mb       = serializers.ReadOnlyField()
    uploaded_by_name   = serializers.CharField(source='uploaded_by.username', read_only=True)
    file_url           = serializers.SerializerMethodField()
    tile_url           = serializers.SerializerMethodField()

    class Meta:
        model  = MBTilesFile
        fields = [
            'id', 'name', 'description', 'file_url', 'tile_url',
            'file_size', 'file_size_mb', 'min_zoom', 'max_zoom',
            'bounds', 'center', 'is_active',
            'uploaded_by', 'uploaded_by_name', 'uploaded_at',
        ]
        read_only_fields = ['id', 'file_size', 'uploaded_by', 'uploaded_at',
                            'min_zoom', 'max_zoom', 'bounds', 'center']

    def get_file_url(self, obj):
        request = self.context.get('request')
        if request and obj.file:
            return request.build_absolute_uri(obj.file.url)
        return None

    def get_tile_url(self, obj):
        request = self.context.get('request')
        if request:
            import urllib.parse
            # Use {z}/{x}/{y} as Leaflet template placeholders (not Python format vars)
            encoded_url = request.build_absolute_uri(
                f'/api/mbtiles/{obj.pk}/tiles/' + '{z}/{x}/{y}.png'
            )
            return urllib.parse.unquote(encoded_url)
        return None


# ─── Helpers ─────────────────────────────────────────────────────────────────

def extract_mbtiles_metadata(path):
    """Read min/max zoom, bounds, center from MBTiles SQLite file."""
    meta = {}
    try:
        conn = sqlite3.connect(path)
        cur  = conn.cursor()
        cur.execute("SELECT name, value FROM metadata")
        for name, value in cur.fetchall():
            meta[name] = value
        conn.close()
    except Exception:
        pass
    return meta


def flip_y(zoom, y):
    """MBTiles uses TMS (bottom-origin); Leaflet uses XYZ (top-origin)."""
    return (1 << zoom) - 1 - y


_TILE_CACHE_SIZE = int(os.environ.get('MBTILES_CACHE_SIZE', '512'))


@lru_cache(maxsize=_TILE_CACHE_SIZE)
def _get_tile_bytes(file_path: str, z: int, x: int, tms_y: int):
    """Read one tile from an MBTiles SQLite file. Cached in-process by (path, z, x, tms_y)."""
    try:
        conn = sqlite3.connect(file_path)
        cur  = conn.cursor()
        cur.execute(
            'SELECT tile_data FROM tiles WHERE zoom_level=? AND tile_column=? AND tile_row=?',
            (z, x, tms_y)
        )
        row = cur.fetchone()
        conn.close()
        return row[0] if row and row[0] else None
    except Exception:
        return None


# ─── Views ────────────────────────────────────────────────────────────────────

class MBTilesListCreateView(generics.ListCreateAPIView):
    """List all active MBTiles or upload a new one (upload = admin only)."""
    serializer_class   = MBTilesSerializer
    parser_classes     = [MultiPartParser, FormParser]

    def get_permissions(self):
        if self.request.method == 'POST':
            return [permissions.IsAdminUser()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        return MBTilesFile.objects.filter(is_active=True)

    def create(self, request, *args, **kwargs):
        file = request.FILES.get('file')
        if not file:
            return Response({'detail': 'No file provided.'}, status=400)

        # Validate it's actually an MBTiles / SQLite file
        header = file.read(16)
        file.seek(0)
        if not header.startswith(b'SQLite format 3'):
            return Response({'detail': 'File does not appear to be a valid MBTiles (SQLite) file.'}, status=400)

        instance = MBTilesFile(
            name        = request.data.get('name', file.name),
            description = request.data.get('description', ''),
            file        = file,
            uploaded_by = request.user,
        )
        instance.save()

        # Extract metadata from the saved file
        meta = extract_mbtiles_metadata(instance.file.path)
        instance.min_zoom = int(meta.get('minzoom', 0))
        instance.max_zoom = int(meta.get('maxzoom', 18))
        instance.bounds   = meta.get('bounds', '')
        instance.center   = meta.get('center', '')
        instance.save(update_fields=['min_zoom', 'max_zoom', 'bounds', 'center'])

        return Response(
            MBTilesSerializer(instance, context={'request': request}).data,
            status=201
        )


class MBTilesDownloadView(APIView):
    """Stream the raw .mbtiles file to authenticated users."""
    permission_classes = []   # handled manually to support ?token= (Capacitor)

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

    def get(self, request, pk):
        user = self._authenticate(request)
        if not user:
            return HttpResponse(status=401)
        try:
            mbt = MBTilesFile.objects.get(pk=pk, is_active=True)
        except MBTilesFile.DoesNotExist:
            raise Http404
        filename = f'{mbt.name}.mbtiles'
        response = FileResponse(
            open(mbt.file.path, 'rb'),
            content_type='application/x-sqlite3',
            as_attachment=True,
            filename=filename,
        )
        response['Content-Length'] = mbt.file_size
        response['X-Accel-Buffering'] = 'no'   # tell Nginx not to buffer this response
        return response


class MBTilesDetailView(generics.RetrieveDestroyAPIView):
    serializer_class   = MBTilesSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset           = MBTilesFile.objects.all()

    def destroy(self, request, *args, **kwargs):
        obj = self.get_object()
        if request.user.role not in ('admin',) and obj.uploaded_by != request.user:
            return Response({'detail': 'Permission denied.'}, status=403)
        obj.delete()
        return Response(status=204)


class TileView(APIView):
    """
    Serve a single tile from an MBTiles file.
    Auth via Bearer header OR ?token= query param (needed for Leaflet img requests).
    Returns a 1x1 transparent PNG for missing tiles instead of 404 so the map renders cleanly.
    """
    permission_classes = []   # handled manually below to support ?token= param

    # 1x1 transparent PNG
    EMPTY_TILE = (
        b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
        b'\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01'
        b'\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
    )

    def _authenticate(self, request):
        """Accept JWT from Authorization header or ?token= query param."""
        from rest_framework_simplejwt.authentication import JWTAuthentication
        from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

        # Try standard header auth first
        try:
            result = JWTAuthentication().authenticate(request)
            if result:
                return result[0]
        except (InvalidToken, TokenError):
            pass

        # Fall back to ?token= query param (for Leaflet tile URLs)
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

    def get(self, request, pk, z, x, y):
        user = self._authenticate(request)
        if not user:
            return HttpResponse(status=401)

        try:
            mbt = MBTilesFile.objects.get(pk=pk, is_active=True)
        except MBTilesFile.DoesNotExist:
            return HttpResponse(self.EMPTY_TILE, content_type='image/png')

        # Flip Y from XYZ (Leaflet) to TMS (MBTiles)
        tms_y = flip_y(z, y)

        tile_data = _get_tile_bytes(str(mbt.file.path), z, x, tms_y)
        if not tile_data:
            return HttpResponse(self.EMPTY_TILE, content_type='image/png')

        content_type = 'image/png' if tile_data[:4] == b'\x89PNG' else 'image/jpeg'
        response = HttpResponse(tile_data, content_type=content_type)
        response['Cache-Control'] = 'public, max-age=86400'
        return response


# ═══════════════════════════════════════════════════════════════════════════════
# Route Overlay (vector overlays: GeoJSON, GPKG, KML)
# ═══════════════════════════════════════════════════════════════════════════════

class RouteOverlaySerializer(serializers.ModelSerializer):
    file_size_mb     = serializers.ReadOnlyField()
    uploaded_by_name = serializers.CharField(source='uploaded_by.username', read_only=True)
    geojson_url      = serializers.SerializerMethodField()

    class Meta:
        model  = RouteOverlay
        fields = [
            'id', 'name', 'description', 'file_format', 'file_size', 'file_size_mb',
            'feature_count', 'bounds', 'geojson_url', 'is_active',
            'uploaded_by', 'uploaded_by_name', 'uploaded_at',
        ]
        read_only_fields = [
            'id', 'file_format', 'file_size', 'feature_count',
            'bounds', 'uploaded_by', 'uploaded_at',
        ]

    def get_geojson_url(self, obj):
        request = self.context.get('request')
        if request and obj.geojson_file:
            return request.build_absolute_uri(f'/api/overlays/{obj.pk}/geojson/')
        return None


# ─── Conversion helpers ──────────────────────────────────────────────────────

def _extract_bounds(geojson):
    """Extract bounding box string from a GeoJSON FeatureCollection."""
    coords = []

    def _collect(geom):
        t = geom.get('type', '')
        if t == 'Point':
            coords.append(geom['coordinates'][:2])
        elif t in ('LineString', 'MultiPoint'):
            coords.extend(c[:2] for c in geom['coordinates'])
        elif t in ('Polygon', 'MultiLineString'):
            for ring in geom['coordinates']:
                coords.extend(c[:2] for c in ring)
        elif t == 'MultiPolygon':
            for poly in geom['coordinates']:
                for ring in poly:
                    coords.extend(c[:2] for c in ring)

    for f in geojson.get('features', []):
        if f.get('geometry'):
            _collect(f['geometry'])
    if not coords:
        return ''
    lngs = [c[0] for c in coords]
    lats = [c[1] for c in coords]
    return f'{min(lngs)},{min(lats)},{max(lngs)},{max(lats)}'


def _convert_to_geojson(instance):
    """Convert uploaded overlay to GeoJSON. For .geojson files, just validate."""
    src = instance.original_file.path

    if instance.file_format == 'geojson':
        with open(src) as f:
            data = json.load(f)
        instance.geojson_file = instance.original_file
        instance.feature_count = len(data.get('features', []))
    else:
        fd, out_path = tempfile.mkstemp(suffix='.geojson')
        os.close(fd)
        os.unlink(out_path)  # ogr2ogr refuses to overwrite existing files
        try:
            result = subprocess.run(
                ['ogr2ogr', '-f', 'GeoJSON', out_path, src],
                capture_output=True, text=True
            )
            if result.returncode != 0:
                err_msg = (result.stderr or result.stdout or 'unknown error').strip()
                raise RuntimeError(f'ogr2ogr failed: {err_msg}')
            with open(out_path) as f:
                data = json.load(f)
            instance.feature_count = len(data.get('features', []))
            dest = f'overlays/geojson/{instance.pk}.geojson'
            dest_full = os.path.join(settings.MEDIA_ROOT, dest)
            os.makedirs(os.path.dirname(dest_full), exist_ok=True)
            shutil.move(out_path, dest_full)
            instance.geojson_file = dest
        finally:
            if os.path.exists(out_path):
                os.unlink(out_path)

    instance.bounds = _extract_bounds(data)
    instance.save(update_fields=['geojson_file', 'feature_count', 'bounds'])


# ─── Overlay views ───────────────────────────────────────────────────────────

class RouteOverlayListCreateView(generics.ListCreateAPIView):
    """List all active overlays or upload a new one (upload = admin only)."""
    serializer_class  = RouteOverlaySerializer
    parser_classes     = [MultiPartParser, FormParser]

    def get_permissions(self):
        if self.request.method == 'POST':
            return [permissions.IsAdminUser()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        return RouteOverlay.objects.filter(is_active=True)

    def create(self, request, *args, **kwargs):
        # Catch Django multipart parser exceptions (file count / memory limits)
        # before they escape as unformatted HTML responses
        try:
            file = request.FILES.get('file')
        except (SuspiciousOperation, RequestDataTooBig) as e:
            return Response({'detail': str(e)}, status=400)

        if not file:
            return Response({'detail': 'No file provided.'}, status=400)

        ext = file.name.rsplit('.', 1)[-1].lower()
        format_map = {'geojson': 'geojson', 'json': 'geojson', 'gpkg': 'gpkg', 'kml': 'kml'}
        fmt = format_map.get(ext)
        if not fmt:
            return Response(
                {'detail': 'Unsupported format. Use .geojson, .gpkg, or .kml'},
                status=400
            )

        instance = RouteOverlay(
            name=request.data.get('name', file.name.rsplit('.', 1)[0]),
            description=request.data.get('description', ''),
            original_file=file,
            file_format=fmt,
            file_size=file.size,
            uploaded_by=request.user,
        )
        instance.save()

        try:
            _convert_to_geojson(instance)
        except Exception as e:
            instance.delete()
            return Response({'detail': f'Conversion failed: {e}'}, status=400)

        return Response(
            RouteOverlaySerializer(instance, context={'request': request}).data,
            status=201
        )


class RouteOverlayDetailView(generics.RetrieveDestroyAPIView):
    serializer_class  = RouteOverlaySerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset           = RouteOverlay.objects.all()

    def destroy(self, request, *args, **kwargs):
        obj = self.get_object()
        if request.user.role not in ('admin',) and obj.uploaded_by != request.user:
            return Response({'detail': 'Permission denied.'}, status=403)
        obj.delete()
        return Response(status=204)


class RouteOverlayGeoJSONView(APIView):
    """Serve the GeoJSON content for a route overlay."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        try:
            overlay = RouteOverlay.objects.get(pk=pk, is_active=True)
        except RouteOverlay.DoesNotExist:
            raise Http404
        if not overlay.geojson_file:
            return Response({'detail': 'GeoJSON not available'}, status=404)
        with open(overlay.geojson_file.path, 'r') as f:
            data = f.read()
        return HttpResponse(data, content_type='application/json')
