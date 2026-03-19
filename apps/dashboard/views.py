from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, FormView, TemplateView, UpdateView
import json

from apps.companies.forms import OrganizationForm
from apps.companies.models import Organization

from .forms import UserPlanUpdateForm


class UserOrganizationQuerysetMixin(LoginRequiredMixin):
    def get_queryset(self):
        queryset = Organization.objects.select_related("owner", "subscription")
        if self.request.user.is_superuser:
            return queryset
        return queryset.filter(owner=self.request.user)

    def current_organization_count(self) -> int:
        return self.get_queryset().count()

    def current_organization_limit(self) -> int | None:
        if self.request.user.is_superuser:
            return None
        return self.request.user.organization_limit()

    def can_create_organization(self) -> bool:
        if self.request.user.is_superuser:
            return True
        return self.request.user.can_add_organization(self.current_organization_count())


class DashboardHomeView(UserOrganizationQuerysetMixin, TemplateView):
    template_name = "dashboard/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        organizations = self.get_queryset()
        context["organizations"] = organizations
        context["organization_count"] = organizations.count()
        context["organization_limit"] = self.current_organization_limit()
        context["can_create_organization"] = self.can_create_organization()
        return context


class OrganizationCreateView(UserOrganizationQuerysetMixin, CreateView):
    model = Organization
    form_class = OrganizationForm
    template_name = "dashboard/organization_form.html"
    success_url = reverse_lazy("dashboard:home")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not self.can_create_organization():
            if request.LANGUAGE_CODE == "pl":
                messages.warning(request, "Osiągnięto limit stron dla Twojego planu.")
            else:
                messages.warning(request, "Your plan page limit has been reached.")
            return redirect("dashboard:home")
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["language_code"] = self.request.LANGUAGE_CODE
        from apps.subscriptions.models import PlanTier, PLAN_FEATURES
        tier_key = self.request.user.plan_tier or PlanTier.BASIC

        class SubscriptionHint:
            def feature_matrix(self):
                return PLAN_FEATURES.get(
                    tier_key,
                    PLAN_FEATURES[PlanTier.BASIC]
                )

        class OrganizationHint:
            def get_subscription(self):
                return SubscriptionHint()

        organization_hint = OrganizationHint()
        kwargs["organization"] = organization_hint
        return kwargs

    def form_valid(self, form):
        form.instance.owner = self.request.user
        messages.success(self.request, "Organization profile saved.")
        return super().form_valid(form)


class OrganizationUpdateView(UserOrganizationQuerysetMixin, UpdateView):
    model = Organization
    form_class = OrganizationForm
    template_name = "dashboard/organization_form.html"
    success_url = reverse_lazy("dashboard:home")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["language_code"] = self.request.LANGUAGE_CODE
        kwargs["organization"] = self.object
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, "Organization profile updated.")
        return super().form_valid(form)


class OrganizationDeleteView(UserOrganizationQuerysetMixin, View):
    def post(self, request, pk, *args, **kwargs):
        organization = get_object_or_404(self.get_queryset(), pk=pk)
        organization_name = organization.name
        organization.delete()

        if request.LANGUAGE_CODE == "pl":
            messages.success(request, f"Usunięto stronę: {organization_name}.")
        else:
            messages.success(request, f"Deleted company page: {organization_name}.")

        return redirect("dashboard:home")

    def get(self, request, *args, **kwargs):
        return redirect("dashboard:home")


class PlanUpdateView(LoginRequiredMixin, FormView):
    form_class = UserPlanUpdateForm
    template_name = "dashboard/plan_form.html"
    success_url = reverse_lazy("dashboard:home")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_superuser:
            if request.LANGUAGE_CODE == "pl":
                messages.info(request, "Konto administratora nie korzysta z limitów planów.")
            else:
                messages.info(request, "Administrator account does not use plan limits.")
            return redirect("dashboard:home")
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["current_organization_count"] = self.request.user.organizations.count()
        context["current_organization_limit"] = self.request.user.organization_limit()
        return context

    def form_valid(self, form):
        selected_tier = form.cleaned_data["plan_tier"]
        if self.request.user.plan_tier != selected_tier:
            self.request.user.plan_tier = selected_tier
            self.request.user.save(update_fields=["plan_tier"])
            if self.request.LANGUAGE_CODE == "pl":
                messages.success(self.request, "Plan został zaktualizowany.")
            else:
                messages.success(self.request, "Plan updated successfully.")
        else:
            if self.request.LANGUAGE_CODE == "pl":
                messages.info(self.request, "Wybrany plan jest już aktywny.")
            else:
                messages.info(self.request, "This plan is already active.")
        return super().form_valid(form)

