from rest_framework import generics

from apps.accounts.permissions import IsAdministrator
from apps.core.models import AuditLog, record_audit
from apps.machines.models import Machine
from apps.machines.serializers import MachineSerializer


class MachineListCreateAPIView(generics.ListCreateAPIView):
    serializer_class = MachineSerializer
    pagination_class = None

    def get_queryset(self):
        return Machine.objects.all()

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAdministrator()]
        return super().get_permissions()

    def perform_create(self, serializer):
        machine = serializer.save()
        record_audit(self.request.user, AuditLog.ACTION_MACHINE_CREATE, machine.machine_id)
