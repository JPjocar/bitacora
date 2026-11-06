from django.contrib import admin

from apps.core.admin import ReadOnlyAdmin

from .models import (
    Maintenance,
    MaintenanceEvent,
    MaintenanceRun,
    MaintenanceRunDevice,
    MaintenanceTarget,
    MaintenanceTaskResult,
    MaintenanceTaskTemplate,
)

for model in (
    Maintenance,
    MaintenanceTarget,
    MaintenanceTaskTemplate,
    MaintenanceRun,
    MaintenanceRunDevice,
    MaintenanceTaskResult,
    MaintenanceEvent,
):
    admin.site.register(model, ReadOnlyAdmin)
