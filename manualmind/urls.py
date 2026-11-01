from django.contrib import admin
from django.urls import include, path

from apps.core.views import health

urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", health, name="health"),
    path("api/v1/auth/", include("apps.accounts.api_urls")),
    path("api/v1/machines/", include("apps.machines.api_urls")),
    path("api/v1/manuals/", include("apps.manuals.api_urls")),
    path("api/v1/assistant/", include("apps.assistant.api_urls")),
    path("api/v1/supervisor/", include("apps.supervisor.api_urls")),
    path("", include("apps.core.urls")),
    path("", include("apps.accounts.urls")),
    path("", include("apps.manuals.urls")),
    path("", include("apps.assistant.urls")),
    path("", include("apps.supervisor.urls")),
]
