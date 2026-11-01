from django.urls import path

from apps.supervisor.views import supervisor_log

urlpatterns = [path("supervisor/log/", supervisor_log, name="supervisor_log")]
