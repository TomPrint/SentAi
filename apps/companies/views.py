from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ContentEntry, Organization, Product, SocialProfile, Tag
from .permissions import IsOrganizationOwnerOrAdmin
from .serializers import (
    ContentEntrySerializer,
    OrganizationSerializer,
    ProductSerializer,
    SocialProfileSerializer,
    TagSerializer,
)
from .services import build_basic_feed, build_jsonld_feed, build_llms_text


class OwnedOrganizationQuerysetMixin:
    def get_organization_queryset(self):
        queryset = Organization.objects.select_related("owner", "subscription")
        if self.request.user.is_superuser:
            return queryset
        return queryset.filter(owner=self.request.user)


class OrganizationListCreateView(OwnedOrganizationQuerysetMixin, generics.ListCreateAPIView):
    serializer_class = OrganizationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return self.get_organization_queryset()

    def perform_create(self, serializer):
        if not self.request.user.is_superuser:
            current_count = self.get_organization_queryset().count()
            if not self.request.user.can_add_organization(current_count):
                limit = self.request.user.organization_limit()
                raise ValidationError(
                    {"plan": f"The {self.request.user.plan_tier} plan allows up to {limit} company pages."}
                )
        serializer.save(owner=self.request.user)


class OrganizationDetailView(OwnedOrganizationQuerysetMixin, generics.RetrieveUpdateAPIView):
    serializer_class = OrganizationSerializer
    permission_classes = [permissions.IsAuthenticated, IsOrganizationOwnerOrAdmin]

    def get_queryset(self):
        return self.get_organization_queryset()


class OrganizationResourceMixin(OwnedOrganizationQuerysetMixin):
    relation_name = ""

    def get_organization(self):
        if not hasattr(self, "_organization"):
            self._organization = get_object_or_404(
                self.get_organization_queryset(),
                pk=self.kwargs["organization_pk"],
            )
        return self._organization

    def get_queryset(self):
        return getattr(self.get_organization(), self.relation_name).all()

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["organization"] = self.get_organization()
        return context

    def perform_create(self, serializer):
        serializer.save(organization=self.get_organization())


class SocialProfileListCreateView(OrganizationResourceMixin, generics.ListCreateAPIView):
    serializer_class = SocialProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    relation_name = "social_profiles"


class SocialProfileDetailView(OrganizationResourceMixin, generics.RetrieveUpdateDestroyAPIView):
    serializer_class = SocialProfileSerializer
    permission_classes = [permissions.IsAuthenticated, IsOrganizationOwnerOrAdmin]
    relation_name = "social_profiles"


class TagListCreateView(OrganizationResourceMixin, generics.ListCreateAPIView):
    serializer_class = TagSerializer
    permission_classes = [permissions.IsAuthenticated]
    relation_name = "tags"


class TagDetailView(OrganizationResourceMixin, generics.RetrieveUpdateDestroyAPIView):
    serializer_class = TagSerializer
    permission_classes = [permissions.IsAuthenticated, IsOrganizationOwnerOrAdmin]
    relation_name = "tags"


class ProductListCreateView(OrganizationResourceMixin, generics.ListCreateAPIView):
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticated]
    relation_name = "products"


class ProductDetailView(OrganizationResourceMixin, generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticated, IsOrganizationOwnerOrAdmin]
    relation_name = "products"


class ContentEntryListCreateView(OrganizationResourceMixin, generics.ListCreateAPIView):
    serializer_class = ContentEntrySerializer
    permission_classes = [permissions.IsAuthenticated]
    relation_name = "content_entries"


class ContentEntryDetailView(OrganizationResourceMixin, generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ContentEntrySerializer
    permission_classes = [permissions.IsAuthenticated, IsOrganizationOwnerOrAdmin]
    relation_name = "content_entries"


class PublicOrganizationMixin:
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get_organization(self):
        queryset = Organization.objects.select_related("subscription").prefetch_related(
            "social_profiles",
            "tags",
            "products",
            "content_entries",
        )
        return get_object_or_404(
            queryset,
            slug=self.kwargs["slug"],
            public=True,
            allow_ai_indexing=True,
        )


class PublicCompanyJsonView(PublicOrganizationMixin, APIView):
    def get(self, request, *args, **kwargs):
        organization = self.get_organization()
        return Response(build_basic_feed(organization, request))


class PublicCompanyJsonLdView(PublicOrganizationMixin, APIView):
    def get(self, request, *args, **kwargs):
        organization = self.get_organization()
        if not organization.get_subscription().supports("advanced_formats"):
            raise Http404()
        return Response(build_jsonld_feed(organization, request), content_type="application/ld+json")


class PublicLLMsTextView(PublicOrganizationMixin, APIView):
    def get(self, request, *args, **kwargs):
        organization = self.get_organization()
        if not organization.get_subscription().supports("llms_txt"):
            raise Http404()
        return HttpResponse(build_llms_text(organization, request), content_type="text/plain; charset=utf-8")
