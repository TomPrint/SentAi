from django.contrib import admin

from .models import Subscription


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ("organization", "tier", "status", "started_at", "renews_at")
    list_filter = ("tier", "status")
    search_fields = ("organization__name", "organization__slug")
