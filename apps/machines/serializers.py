from rest_framework import serializers

from apps.machines.models import Machine


class MachineSerializer(serializers.ModelSerializer):
    manual_count = serializers.SerializerMethodField()

    class Meta:
        model = Machine
        fields = [
            "id",
            "machine_id",
            "model",
            "name",
            "plant",
            "is_active",
            "created_at",
            "manual_count",
        ]
        read_only_fields = ["id", "created_at", "manual_count"]

    def get_manual_count(self, obj: Machine) -> int:
        return obj.manuals.filter(is_active=True, status="INDEXED").count()
