from django.contrib import admin

from apps.assistant.models import QueryCitation, QueryLog


class QueryCitationInline(admin.TabularInline):
    model = QueryCitation
    extra = 0


@admin.register(QueryLog)
class QueryLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "machine", "status", "top_score", "llm_model")
    list_filter = ("status", "machine")
    search_fields = ("question", "answer_text")
    inlines = [QueryCitationInline]
