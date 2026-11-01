from django.urls import path

from apps.manuals.views import (
    ManualListCreateAPIView,
    ManualReindexAPIView,
    manual_page_preview,
    manual_pdf,
)

urlpatterns = [
    path("", ManualListCreateAPIView.as_view(), name="api_manual_list"),
    path("<int:pk>/reindex/", ManualReindexAPIView.as_view(), name="api_manual_reindex"),
    path("<int:pk>/pdf/", manual_pdf, name="api_manual_pdf"),
    path(
        "<int:pk>/page/<int:page_number>/preview/",
        manual_page_preview,
        name="api_manual_page_preview",
    ),
]
