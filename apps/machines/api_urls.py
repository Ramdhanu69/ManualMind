from django.urls import path

from apps.machines.views import MachineListCreateAPIView

urlpatterns = [path("", MachineListCreateAPIView.as_view(), name="api_machines")]
