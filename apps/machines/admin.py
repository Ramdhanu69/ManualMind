from django.contrib import admin

from apps.machines.models import Machine


@admin.register(Machine)
class MachineAdmin(admin.ModelAdmin):
    list_display = ("machine_id", "model", "name", "plant", "is_active")
    search_fields = ("machine_id", "model", "name")
