from rest_framework import serializers

from apps.machines.models import Machine
from apps.manuals.models import Manual


class ManualSerializer(serializers.ModelSerializer):
    machine_id = serializers.CharField(source="machine.machine_id", read_only=True)
    machine_model = serializers.CharField(source="machine.model", read_only=True)
    chunk_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Manual
        fields = [
            "id",
            "document_id",
            "machine_id",
            "machine_model",
            "title",
            "revision",
            "status",
            "error_message",
            "page_count",
            "chunk_count",
            "is_active",
            "created_at",
        ]


class ManualUploadSerializer(serializers.Serializer):
    """Upload metadata. `machine` is the machine_id slug, as used everywhere else."""

    machine = serializers.SlugRelatedField(
        slug_field="machine_id", queryset=Machine.objects.all()
    )
    document_id = serializers.CharField(max_length=64)
    title = serializers.CharField(max_length=255)
    revision = serializers.CharField(max_length=32)
    file = serializers.FileField()

    def validate_document_id(self, value: str) -> str:
        return value.strip()

    def validate_revision(self, value: str) -> str:
        return value.strip()
