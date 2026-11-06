from django.contrib import admin
from django.contrib.auth.models import Group

from apps.core.admin import ReadOnlyAdmin

from .models import User, UserEvent

admin.site.unregister(Group)


@admin.register(User)
class UserAdmin(ReadOnlyAdmin):
    fields = (
        "username",
        "first_name",
        "last_name",
        "email",
        "is_active",
        "is_staff",
        "is_superuser",
        "groups",
    )
    list_display = ("username", "is_active", "is_staff")
    search_fields = ("username", "first_name", "last_name")


@admin.register(UserEvent)
class UserEventAdmin(ReadOnlyAdmin):
    list_display = ("created_at", "subject", "actor", "action")
