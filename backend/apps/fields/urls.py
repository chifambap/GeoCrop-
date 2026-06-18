from django.urls import path
from .views import (
    FieldEntryListCreateView, FieldEntryDetailView,
    FieldsGeoJSONView, FieldPhotoUploadView,
    ValidationCreateView, stats_view, ExportFieldsView,
)

urlpatterns = [
    path('export/',        ExportFieldsView.as_view(),         name='field-export'),
    path('',               FieldEntryListCreateView.as_view(), name='field-list'),
    path('<int:pk>/',      FieldEntryDetailView.as_view(),     name='field-detail'),
    path('geojson/',       FieldsGeoJSONView.as_view(),        name='field-geojson'),
    path('<int:pk>/photos/',    FieldPhotoUploadView.as_view(),   name='field-photos'),
    path('<int:pk>/validate/',  ValidationCreateView.as_view(),   name='field-validate'),
    path('stats/',         stats_view,                         name='field-stats'),
]
