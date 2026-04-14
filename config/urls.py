from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path("admin/", admin.site.urls),
    # API v1
    path("api/v1/", include("apps.accounts.urls")),
    path("api/v1/", include("apps.surveys.urls")),
    path("api/v1/", include("apps.responses.urls")),
    path("api/v1/", include("apps.analytics.urls")),
    path("api/v1/", include("apps.audit.urls")),
    # API Documentation
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
]
