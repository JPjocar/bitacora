from django.contrib import admin

from apps.core.admin import ReadOnlyAdmin

from .models import Notification

admin.site.register(Notification, ReadOnlyAdmin)
