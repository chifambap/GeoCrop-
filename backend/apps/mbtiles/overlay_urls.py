from django.urls import path
from .views import RouteOverlayListCreateView, RouteOverlayDetailView, RouteOverlayGeoJSONView

urlpatterns = [
    path('',                  RouteOverlayListCreateView.as_view(), name='overlay-list'),
    path('<int:pk>/',         RouteOverlayDetailView.as_view(),     name='overlay-detail'),
    path('<int:pk>/geojson/', RouteOverlayGeoJSONView.as_view(),    name='overlay-geojson'),
]
