from django.contrib import admin

from apps.manuals.models import Chunk, Manual


@admin.register(Manual)
class ManualAdmin(admin.ModelAdmin):
    list_display = (
        "document_id",
        "revision",
        "machine",
        "title",
        "status",
        "page_count",
        "is_active",
        "created_at",
    )
    list_filter = ("status", "is_active", "machine")
    search_fields = ("document_id", "title")


@admin.register(Chunk)
class ChunkAdmin(admin.ModelAdmin):
    list_display = ("manual", "page_number", "section_title", "char_start", "char_end")
    list_filter = ("machine", "manual")
