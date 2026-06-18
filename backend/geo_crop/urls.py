import os
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView, RedirectView
from django.http import HttpResponse, JsonResponse


def robots_txt(request):
    return HttpResponse("User-agent: *\nDisallow: /\n", content_type="text/plain")


def app_version_view(request):
    return JsonResponse({
        'version_code': int(os.environ.get('APP_VERSION_CODE', 1)),
        'version_name': os.environ.get('APP_VERSION_NAME', '1.0.0'),
        'download_url': '/download/GeoCrop.apk',
    })


admin.site.site_header = 'ZINGSA Geo-Crop Collector Portal Management'
admin.site.site_title = 'ZINGSA Admin'
admin.site.index_title = 'Portal Management'

urlpatterns = [
    path('robots.txt', robots_txt, name='robots-txt'),
    path('', RedirectView.as_view(url='/dashboard/', permanent=False), name='index'),
    path('gcp-manage-portal-internal-developer-access-gateway/', admin.site.urls),
    path('dashboard/', TemplateView.as_view(template_name='dashboard.html'), name='dashboard'),

    # Auth
    path('api/auth/', include('apps.accounts.urls')),

    # Core data
    path('api/',         include('apps.fields.survey_urls')),
    path('api/fields/',  include('apps.fields.urls')),
    path('api/mbtiles/',   include('apps.mbtiles.urls')),
    path('api/overlays/',  include('apps.mbtiles.overlay_urls')),
    path('api/sync/',    include('apps.sync.urls')),
    path('api/app/version/', app_version_view, name='app-version'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

