from django.urls import path

from apps.assistant.views import engineer_ask, engineer_history

urlpatterns = [
    path("ask/", engineer_ask, name="engineer_ask"),
    path("history/", engineer_history, name="engineer_history"),
]
