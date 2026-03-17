from django.urls import path

from .views import (
    DashboardHomeView,
    OrganizationCreateView,
    OrganizationDeleteView,
    OrganizationUpdateView,
    PlanUpdateView,
)


app_name = "dashboard"

urlpatterns = [
    path("", DashboardHomeView.as_view(), name="home"),
    path("plan/", PlanUpdateView.as_view(), name="plan-update"),
    path("organizations/new/", OrganizationCreateView.as_view(), name="organization-create"),
    path("organizations/<int:pk>/edit/", OrganizationUpdateView.as_view(), name="organization-edit"),
    path("organizations/<int:pk>/delete/", OrganizationDeleteView.as_view(), name="organization-delete"),
]

