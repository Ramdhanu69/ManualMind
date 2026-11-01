from rest_framework import serializers

from apps.assistant.models import QueryCitation, QueryLog


class QueryCitationSerializer(serializers.ModelSerializer):
    manual_id = serializers.IntegerField(read_only=True)
    title = serializers.CharField(source="manual.title", read_only=True, default="")

    class Meta:
        model = QueryCitation
        fields = [
            "manual_id",
            "document_id",
            "title",
            "revision",
            "page_number",
            "quote",
            "quote_verified",
            "order",
        ]


class QueryLogSerializer(serializers.ModelSerializer):
    machine_id = serializers.CharField(source="machine.machine_id", read_only=True)
    machine_model = serializers.CharField(source="machine.model", read_only=True)
    username = serializers.CharField(source="user.username", read_only=True, default="")
    citations = QueryCitationSerializer(many=True, read_only=True)
    latency_ms_total = serializers.IntegerField(read_only=True)

    class Meta:
        model = QueryLog
        fields = [
            "id",
            "machine_id",
            "machine_model",
            "username",
            "question",
            "answer_text",
            "status",
            "top_score",
            "llm_provider",
            "llm_model",
            "embedding_model",
            "latency_ms_retrieval",
            "latency_ms_llm",
            "latency_ms_total",
            "created_at",
            "citations",
        ]


class AskSerializer(serializers.Serializer):
    machine_id = serializers.CharField(max_length=64)
    question = serializers.CharField(max_length=1000, trim_whitespace=True)

    def validate_question(self, value: str) -> str:
        cleaned = " ".join(value.split())
        if len(cleaned) < 3:
            raise serializers.ValidationError("Enter a question of at least 3 characters.")
        return cleaned
