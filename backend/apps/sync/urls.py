"""
Sync API — allows devices to push batches of field entries and pull changes
since a given timestamp. Idempotent via client_uuid.
"""
from django.urls import path
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.fields.models import FieldEntry, ValidationRecord
from apps.fields.serializers import FieldEntrySerializer


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def push_view(request):
    """
    Device pushes an array of feature objects it collected offline.
    Each entry must include a unique `client_uuid` to prevent duplicates.
    Optionally includes validation data per entry.

    POST /api/sync/push/
    Body: { "entries": [ <FieldEntry JSON>, ... ] }
    """
    entries = request.data.get('entries', [])
    if not isinstance(entries, list):
        return Response({'detail': '"entries" must be a list.'}, status=400)

    # Single bulk query to find all already-known client_uuids — replaces N per-entry queries
    all_uuids = [item.get('client_uuid') for item in entries if item.get('client_uuid')]
    existing_uuids = {
        str(u) for u in
        FieldEntry.objects.filter(client_uuid__in=all_uuids)
                          .values_list('client_uuid', flat=True)
    }

    created_ids = []
    skipped     = []
    errors      = []

    for i, item in enumerate(entries):
        uuid = item.get('client_uuid')
        if uuid and str(uuid) in existing_uuids:  # O(1) set lookup, no DB hit
            skipped.append(uuid)
            continue

        # Pop validation data before passing to serializer (not a model field)
        validation_data = item.pop('validation', None)

        serializer = FieldEntrySerializer(data=item, context={'request': request})
        if serializer.is_valid():
            obj = serializer.save(collected_by=request.user)
            created_ids.append(obj.pk)

            # Create ValidationRecord if validation data was included
            if validation_data and isinstance(validation_data, dict):
                v_status = validation_data.get('status', '')
                v_confidence = validation_data.get('confidence')
                if v_status and v_confidence:
                    try:
                        ValidationRecord.objects.create(
                            field=obj,
                            validated_by=request.user,
                            status=v_status,
                            confidence=int(v_confidence),
                            note=validation_data.get('note', ''),
                        )
                    except Exception:
                        pass  # Don't fail the whole sync for a validation issue
        else:
            errors.append({'index': i, 'errors': serializer.errors})

    return Response({
        'created': len(created_ids),
        'skipped': len(skipped),
        'errors':  errors,
        'ids':     created_ids,
    }, status=207 if errors else 201)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def pull_view(request):
    """
    Device pulls all entries updated since a given ISO timestamp.

    GET /api/sync/pull/?since=2024-01-01T00:00:00Z
    Returns entries the device doesn't have yet.
    """
    since = request.query_params.get('since')
    qs = FieldEntry.objects.select_related('collected_by', 'validation') \
                           .prefetch_related('photos')

    if request.user.role not in ('admin', 'validator'):
        qs = qs.filter(collected_by=request.user)

    if since:
        try:
            from datetime import datetime
            dt = datetime.fromisoformat(since.replace('Z', '+00:00'))
            qs = qs.filter(updated_at__gt=dt)
        except ValueError:
            return Response({'detail': 'Invalid `since` timestamp. Use ISO 8601.'}, status=400)

    from django.conf import settings
    total = qs.count()
    cap = settings.SYNC_PULL_MAX_ROWS
    has_more = total > cap

    serializer = FieldEntrySerializer(qs[:cap], many=True, context={'request': request})
    return Response({
        'count':     min(total, cap),
        'total':     total,
        'has_more':  has_more,
        'server_ts': timezone.now().isoformat(),
        'entries':   serializer.data,
    })


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def sync_status_view(request):
    """Quick status endpoint for the device to check connectivity + token validity."""
    return Response({
        'ok':        True,
        'user':      request.user.username,
        'role':      request.user.role,
        'server_ts': timezone.now().isoformat(),
    })


urlpatterns = [
    path('push/',   push_view,        name='sync-push'),
    path('pull/',   pull_view,        name='sync-pull'),
    path('status/', sync_status_view, name='sync-status'),
]
