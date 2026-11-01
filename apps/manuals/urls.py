from django.urls import path

from apps.manuals.views import admin_console

urlpatterns = [path("admin-console/", admin_console, name="admin_console")]
