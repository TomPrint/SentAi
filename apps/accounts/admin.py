from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class SentAiUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        (
            "SentAi",
            {
                "fields": (
                    "company_name",
                    "preferred_language",
                    "account_type",
                    "plan_tier",
                )
            },
        ),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        (
            "SentAi",
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
        "preferred_language",
        "is_staff",
        "is_superuser",
    )
    search_fields = ("username", "email", "company_name")
