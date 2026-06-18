from django.urls import path
from .views import MBTilesListCreateView, MBTilesDetailView, MBTilesDownloadView, TileView

urlpatterns = [
    path('',                                    MBTilesListCreateView.as_view(), name='mbtiles-list'),
    path('<int:pk>/',                           MBTilesDetailView.as_view(),     name='mbtiles-detail'),
    path('<int:pk>/download/',                  MBTilesDownloadView.as_view(),   name='mbtiles-download'),
    path('<int:pk>/tiles/<int:z>/<int:x>/<int:y>.png', TileView.as_view(),      name='mbtiles-tile'),
]
