from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class XoailaUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        (
            "Xoaila",
            {
                "fields": (
                    "company_name",
                    "preferred_language",
                    "account_type",
                    "plan_tier",
                    "plan_access_status",
                )
            },
        ),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        (
            "Xoaila",
            {
                "fields": (
                    "email",
                    "company_name",
                    "preferred_language",
                    "account_type",
                    "plan_tier",
                )
            },
        ),
    )
    list_display = (
        "username",
        "email",
        "account_type",
        "plan_tier",
        "plan_access_status",
        "preferred_language",
        "is_staff",
        "is_superuser",
    )
    readonly_fields = ("plan_access_status",)
    search_fields = ("username", "email", "company_name")
