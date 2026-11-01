from django.urls import path

from apps.assistant.views import AskAPIView, HistoryDetailAPIView, HistoryListAPIView

urlpatterns = [
    path("ask/", AskAPIView.as_view(), name="api_ask"),
    path("history/", HistoryListAPIView.as_view(), name="api_history"),
    path("history/<int:pk>/", HistoryDetailAPIView.as_view(), name="api_history_detail"),
]
