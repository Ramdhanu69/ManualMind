from django.urls import path

from apps.supervisor.views import KnowledgeGapsAPIView, SupervisorStatsAPIView

urlpatterns = [
    path("knowledge-gaps/", KnowledgeGapsAPIView.as_view(), name="api_knowledge_gaps"),
    path("stats/", SupervisorStatsAPIView.as_view(), name="api_supervisor_stats"),
]
