from django.contrib import admin

from apps.core.admin import ReadOnlyAdmin

from .models import Incident, IncidentEvent

admin.site.register(Incident, ReadOnlyAdmin)
admin.site.register(IncidentEvent, ReadOnlyAdmin)
