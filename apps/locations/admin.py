from django.contrib import admin

from apps.core.admin import ReadOnlyAdmin

from .models import Location, LocationEvent


@admin.register(Location)
class LocationAdmin(ReadOnlyAdmin):
    list_display = ("name", "code", "kind", "is_active")
    list_filter = ("kind", "is_active")
    search_fields = ("name", "code")


@admin.register(LocationEvent)
class LocationEventAdmin(ReadOnlyAdmin):
    list_display = ("created_at", "location", "actor", "action")
