from django.contrib import admin

from apps.core.admin import ReadOnlyAdmin

from .models import Category, CategoryEvent, Device, DeviceEvent, Movement


@admin.register(Device)
class DeviceAdmin(ReadOnlyAdmin):
    exclude = ("commissioned_on",)
    list_display = ("code", "name", "category", "location", "status", "is_active")
    search_fields = ("code", "name")


@admin.register(Movement)
class MovementAdmin(ReadOnlyAdmin):
    list_display = ("device", "origin", "destination", "effective_at", "actor")
    list_select_related = ("device", "origin", "destination", "actor")


admin.site.register(Category, ReadOnlyAdmin)
admin.site.register(CategoryEvent, ReadOnlyAdmin)
admin.site.register(DeviceEvent, ReadOnlyAdmin)
