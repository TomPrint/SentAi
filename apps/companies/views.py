import datetime
import hashlib
import json
from xml.sax.saxutils import escape

from django.conf import settings
from django.http import Http404, HttpResponse, StreamingHttpResponse
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.dateparse import parse_datetime
from django.utils.timezone import is_aware, make_aware
from django.views.generic import TemplateView
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters as drf_filters
from rest_framework import generics, permissions
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView
import django_filters

from .models import ContentEntry, Organization, Product, SocialProfile, Tag, VerificationStatus
from .permissions import IsOrganizationOwnerOrAdmin
from .serializers import (
    ContentEntrySerializer,
    OrganizationSerializer,
    ProductSerializer,
    SocialProfileSerializer,
    TagSerializer,
)
from drf_spectacular.utils import extend_schema

from .services import build_basic_feed, build_jsonld_feed, build_llms_text, build_markdown_feed, public_feed_urls


class OwnedOrganizationQuerysetMixin:
    def get_organization_queryset(self):
        queryset = Organization.objects.select_related("owner", "subscription")
        if self.request.user.is_superuser:
            return queryset
        return queryset.filter(owner=self.request.user)


@extend_schema(exclude=True)
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


@extend_schema(exclude=True)
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


@extend_schema(exclude=True)
class SocialProfileListCreateView(OrganizationResourceMixin, generics.ListCreateAPIView):
    serializer_class = SocialProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    relation_name = "social_profiles"


@extend_schema(exclude=True)
class SocialProfileDetailView(OrganizationResourceMixin, generics.RetrieveUpdateDestroyAPIView):
    serializer_class = SocialProfileSerializer
    permission_classes = [permissions.IsAuthenticated, IsOrganizationOwnerOrAdmin]
    relation_name = "social_profiles"


@extend_schema(exclude=True)
class TagListCreateView(OrganizationResourceMixin, generics.ListCreateAPIView):
    serializer_class = TagSerializer
    permission_classes = [permissions.IsAuthenticated]
    relation_name = "tags"


@extend_schema(exclude=True)
class TagDetailView(OrganizationResourceMixin, generics.RetrieveUpdateDestroyAPIView):
    serializer_class = TagSerializer
    permission_classes = [permissions.IsAuthenticated, IsOrganizationOwnerOrAdmin]
    relation_name = "tags"


@extend_schema(exclude=True)
class ProductListCreateView(OrganizationResourceMixin, generics.ListCreateAPIView):
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticated]
    relation_name = "products"


@extend_schema(exclude=True)
class ProductDetailView(OrganizationResourceMixin, generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticated, IsOrganizationOwnerOrAdmin]
    relation_name = "products"


@extend_schema(exclude=True)
class ContentEntryListCreateView(OrganizationResourceMixin, generics.ListCreateAPIView):
    serializer_class = ContentEntrySerializer
    permission_classes = [permissions.IsAuthenticated]
    relation_name = "content_entries"


@extend_schema(exclude=True)
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


class PublicCompanyDirectoryPageView(TemplateView):
    template_name = "companies/directory.html"

    def get_queryset(self):
        queryset = (
            Organization.objects.filter(
                public=True,
                allow_ai_indexing=True,
                verification_status=VerificationStatus.HUMAN_ADMIN_VERIFIED,
            )
            .select_related("subscription", "owner")
            .prefetch_related("tags")
            .order_by("name")
        )
        query = self.request.GET.get("q", "").strip()
        if query:
            queryset = queryset.filter(
                Q(name__icontains=query)
                | Q(ai_summary__icontains=query)
                | Q(short_description_en__icontains=query)
                | Q(short_description_pl__icontains=query)
                | Q(tags__name__icontains=query)
            ).distinct()
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        paginator = Paginator(self.get_queryset(), 24)
        page_obj = paginator.get_page(self.request.GET.get("page"))
        context["page_obj"] = page_obj
        context["organizations"] = page_obj.object_list
        context["query"] = self.request.GET.get("q", "").strip()
        context["total_count"] = paginator.count
        return context


class PublicCompanyDetailPageView(TemplateView):
    template_name = "companies/detail.html"

    def get_organization(self):
        if not hasattr(self, "_organization"):
            self._organization = get_object_or_404(
                Organization.objects.filter(
                    public=True,
                    allow_ai_indexing=True,
                    verification_status=VerificationStatus.HUMAN_ADMIN_VERIFIED,
                )
                .select_related("subscription", "owner")
                .prefetch_related("social_profiles", "tags", "products", "content_entries"),
                slug=self.kwargs["slug"],
            )
        return self._organization

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        organization = self.get_organization()
        context["organization"] = organization
        context["feed_urls"] = public_feed_urls(organization, self.request)
        context["canonical_url"] = self.request.build_absolute_uri(
            reverse("public-company-detail", kwargs={"slug": organization.slug})
        )
        context["jsonld_payload"] = ""
        if organization.supports_advanced_formats:
            context["jsonld_payload"] = json.dumps(
                build_jsonld_feed(organization, self.request),
                ensure_ascii=False,
            )
        context["description"] = (
            organization.localized_text("long_description", organization.primary_language)
            or organization.localized_text("short_description", organization.primary_language)
            or organization.ai_summary
        )
        context["products"] = organization.products.all()
        context["entries"] = organization.content_entries.all()[:10]
        context["tags"] = organization.tags.all()
        context["social_profiles"] = organization.social_profiles.all()
        return context


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


class PublicCompanyMarkdownView(PublicOrganizationMixin, APIView):
    def get(self, request, *args, **kwargs):
        organization = self.get_organization()
        if not organization.get_subscription().supports("company_md"):
            raise Http404()
        return HttpResponse(
            build_markdown_feed(organization, request),
            content_type="text/markdown; charset=utf-8",
        )


# ---------------------------------------------------------------------------
# Public catalog — no authentication required
# ---------------------------------------------------------------------------

def _catalog_entry(org, request) -> dict:
    sub = org.get_subscription()
    return {
        "name": org.name,
        "slug": org.slug,
        "company_type": org.company_type,
        "company_type_label": org.get_company_type_display(),
        "city": org.city,
        "country": org.country,
        "primary_language": org.primary_language,
        "website_url": org.website_url,
        "ai_summary": org.ai_summary,
        "tags": [tag.name for tag in org.tags.all()],
        "verification_status": org.verification_status,
        "available_formats": {
            "company_json": True,
            "company_jsonld": sub.supports("advanced_formats"),
            "company_md": sub.supports("company_md"),
            "llms_txt": sub.supports("llms_txt"),
        },
        "feed_urls": public_feed_urls(org, request),
        "updated_at": org.updated_at.isoformat(),
    }


class CompanyFilter(django_filters.FilterSet):
    search = django_filters.CharFilter(method="filter_search", label="Search name or description")
    city = django_filters.CharFilter(field_name="city", lookup_expr="icontains")
    country = django_filters.CharFilter(field_name="country", lookup_expr="iexact")
    language = django_filters.CharFilter(field_name="primary_language", lookup_expr="exact")
    company_type = django_filters.CharFilter(field_name="company_type", lookup_expr="exact")
    tag = django_filters.CharFilter(method="filter_tag", label="Filter by tag name")
    verified = django_filters.BooleanFilter(method="filter_verified", label="Verified companies only")
    has_price = django_filters.BooleanFilter(method="filter_has_price", label="Companies with priced products")

    class Meta:
        model = Organization
        fields = ["city", "country", "language", "company_type", "tag", "verified", "has_price"]

    def filter_search(self, queryset, name, value):
        from django.db.models import Q
        return queryset.filter(
            Q(name__icontains=value)
            | Q(ai_summary__icontains=value)
            | Q(short_description_en__icontains=value)
            | Q(short_description_pl__icontains=value)
        )

    def filter_tag(self, queryset, name, value):
        return queryset.filter(tags__name__icontains=value).distinct()

    def filter_verified(self, queryset, name, value):
        from .models import VerificationStatus
        if value:
            return queryset.filter(verification_status=VerificationStatus.HUMAN_ADMIN_VERIFIED)
        return queryset

    def filter_has_price(self, queryset, name, value):
        if value:
            return queryset.filter(products__price_from__isnull=False).distinct()
        return queryset


class CompanyListView(generics.GenericAPIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    filterset_class = CompanyFilter
    filter_backends = [DjangoFilterBackend, drf_filters.OrderingFilter]
    ordering_fields = ["name", "updated_at", "created_at"]
    ordering = ["name"]

    def get_queryset(self):
        return (
            Organization.objects.filter(public=True, allow_ai_indexing=True)
            .select_related("subscription", "owner")
            .prefetch_related("tags")
            .order_by("name")
        )

    def get(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        orgs = page if page is not None else queryset
        results = [_catalog_entry(org, request) for org in orgs]
        if page is not None:
            return self.get_paginated_response(results)
        return Response(results)


class CompanyDetailView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request, slug, *args, **kwargs):
        org = get_object_or_404(
            Organization.objects.select_related("subscription", "owner").prefetch_related(
                "social_profiles", "tags", "products", "content_entries"
            ),
            slug=slug,
            public=True,
            allow_ai_indexing=True,
        )
        response = Response(build_basic_feed(org, request))
        response["Last-Modified"] = org.updated_at.strftime("%a, %d %b %Y %H:%M:%S GMT")
        etag = hashlib.md5(f"{org.slug}{org.updated_at.isoformat()}".encode()).hexdigest()
        response["ETag"] = f'"{etag}"'
        return response


class CompanyUpdatesView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request, *args, **kwargs):
        from django.utils import timezone as tz
        since_str = request.GET.get("since", "").strip()
        if not since_str:
            since = tz.now() - datetime.timedelta(days=7)
            since_str = since.isoformat()
        else:
            since = parse_datetime(since_str)
            if since is None:
                return Response(
                    {"error": "Invalid datetime format. Use ISO 8601, e.g. 2026-01-01T00:00:00Z"},
                    status=400,
                )
            if not is_aware(since):
                since = make_aware(since, datetime.timezone.utc)
        organizations = (
            Organization.objects.filter(
                public=True,
                allow_ai_indexing=True,
                updated_at__gte=since,
            )
            .select_related("subscription", "owner")
            .prefetch_related("tags")
            .order_by("-updated_at")
        )
        results = [_catalog_entry(org, request) for org in organizations]
        return Response({
            "since": since_str,
            "total": len(results),
            "results": results,
        })


class BulkAllJsonView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request, *args, **kwargs):
        from django.utils import timezone
        organizations = (
            Organization.objects.filter(public=True, allow_ai_indexing=True)
            .select_related("subscription", "owner")
            .prefetch_related("tags")
            .order_by("name")
        )
        results = [_catalog_entry(org, request) for org in organizations]
        latest = (
            Organization.objects.filter(public=True, allow_ai_indexing=True)
            .order_by("-updated_at")
            .values_list("updated_at", flat=True)
            .first()
        )
        return Response({
            "meta": {
                "catalog": "sentai-company-catalog",
                "version": "1.0",
                "generated_at": timezone.now().isoformat(),
                "last_updated": latest.isoformat() if latest else None,
                "total": len(results),
            },
            "results": results,
        })


class CatalogNdjsonView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request, *args, **kwargs):
        organizations = (
            Organization.objects.filter(public=True, allow_ai_indexing=True)
            .select_related("subscription", "owner")
            .prefetch_related("social_profiles", "tags", "products", "content_entries")
            .order_by("name")
        )

        def generate():
            for org in organizations:
                yield json.dumps(build_basic_feed(org, request), ensure_ascii=False) + "\n"

        return StreamingHttpResponse(generate(), content_type="application/x-ndjson; charset=utf-8")


class SiteLLMsTextView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request, *args, **kwargs):
        from apps.subscriptions.models import PlanTier
        organizations = (
            Organization.objects.filter(
                public=True,
                allow_ai_indexing=True,
                subscription__tier=PlanTier.PRO,
            )
            .select_related("subscription")
            .order_by("name")
        )
        lines = [
            "# llms.txt — SentAi Company Catalog",
            "# This file lists companies that have opted in to AI indexing at PRO tier.",
            "# Each entry links to a dedicated llms.txt feed for that company.",
            "# Convention: https://llmstxt.org",
            "",
            f"# Companies API: {request.build_absolute_uri(reverse('companies_api:company-list'))}",
            f"# API guide: {request.build_absolute_uri('/api-guide.txt')}",
            f"# OpenAPI schema: {request.build_absolute_uri('/openapi.json')}",
            "",
        ]
        for org in organizations:
            company_llms_url = request.build_absolute_uri(
                reverse("companies_api:public-company-llms", kwargs={"slug": org.slug})
            )
            lines.append(f"## {org.name}")
            if org.ai_summary:
                lines.append(f"> {org.ai_summary}")
            lines.append(f"- llms.txt: {company_llms_url}")
            lines.append("")
        return HttpResponse("\n".join(lines), content_type="text/plain; charset=utf-8")


class ApiGuideTextView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request, *args, **kwargs):
        guide_path = settings.BASE_DIR / "api-guide.txt"
        if not guide_path.exists():
            raise Http404()
        return HttpResponse(
            guide_path.read_text(encoding="utf-8"),
            content_type="text/plain; charset=utf-8",
        )


class RobotsTextView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request, *args, **kwargs):
        lines = [
            "# SentAi crawler policy",
            "# Public company catalog, AI-readable feeds, and API docs are crawlable.",
            "",
            "User-agent: *",
            "Allow: /",
            "",
            "User-agent: OAI-SearchBot",
            "Allow: /",
            "",
            "User-agent: GPTBot",
            "Allow: /",
            "",
            "User-agent: ChatGPT-User",
            "Allow: /",
            "",
            "User-agent: ClaudeBot",
            "Allow: /",
            "",
            "User-agent: Claude-SearchBot",
            "Allow: /",
            "",
            "User-agent: PerplexityBot",
            "Allow: /",
            "",
            "User-agent: Googlebot",
            "Allow: /",
            "",
            "User-agent: Google-Extended",
            "Allow: /",
            "",
            "User-agent: CCBot",
            "Allow: /",
            "",
            f"# LLM index: {request.build_absolute_uri(reverse('site-llms-txt'))}",
            f"# API guide: {request.build_absolute_uri(reverse('api-guide-txt'))}",
            f"# OpenAPI schema: {request.build_absolute_uri(reverse('openapi-schema'))}",
            "",
            f"Sitemap: {request.build_absolute_uri(reverse('sitemap-xml'))}",
            "",
        ]
        return HttpResponse("\n".join(lines), content_type="text/plain; charset=utf-8")


class SitemapXmlView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request, *args, **kwargs):
        urls = [
            {
                "loc": request.build_absolute_uri(reverse("landing")),
                "lastmod": None,
            },
            {
                "loc": request.build_absolute_uri(reverse("site-llms-txt")),
                "lastmod": None,
            },
            {
                "loc": request.build_absolute_uri(reverse("api-guide-txt")),
                "lastmod": None,
            },
            {
                "loc": request.build_absolute_uri(reverse("openapi-schema")),
                "lastmod": None,
            },
            {
                "loc": request.build_absolute_uri(reverse("public-company-directory")),
                "lastmod": None,
            },
            {
                "loc": request.build_absolute_uri(reverse("companies_api:company-list")),
                "lastmod": None,
            },
            {
                "loc": request.build_absolute_uri(reverse("companies_api:public-all-json")),
                "lastmod": None,
            },
            {
                "loc": request.build_absolute_uri(reverse("companies_api:public-catalog-ndjson")),
                "lastmod": None,
            },
        ]

        organizations = (
            Organization.objects.filter(
                public=True,
                allow_ai_indexing=True,
                verification_status=VerificationStatus.HUMAN_ADMIN_VERIFIED,
            )
            .select_related("subscription")
            .order_by("slug")
        )
        for org in organizations:
            lastmod = org.updated_at.date().isoformat()
            urls.append(
                {
                    "loc": request.build_absolute_uri(
                        reverse("public-company-detail", kwargs={"slug": org.slug})
                    ),
                    "lastmod": lastmod,
                }
            )
            urls.append(
                {
                    "loc": request.build_absolute_uri(
                        reverse("companies_api:company-detail", kwargs={"slug": org.slug})
                    ),
                    "lastmod": lastmod,
                }
            )
            feed_urls = public_feed_urls(org, request)
            urls.append({"loc": feed_urls["company_json"], "lastmod": lastmod})

            subscription = org.get_subscription()
            if subscription.supports("advanced_formats"):
                urls.append({"loc": feed_urls["company_jsonld"], "lastmod": lastmod})
            if subscription.supports("company_md"):
                urls.append({"loc": feed_urls["company_md"], "lastmod": lastmod})
            if subscription.supports("llms_txt"):
                urls.append({"loc": feed_urls["llms_txt"], "lastmod": lastmod})

        lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
        ]
        for item in urls:
            lines.append("  <url>")
            lines.append(f"    <loc>{escape(item['loc'])}</loc>")
            if item["lastmod"]:
                lines.append(f"    <lastmod>{item['lastmod']}</lastmod>")
            lines.append("  </url>")
        lines.append("</urlset>")
        return HttpResponse("\n".join(lines), content_type="application/xml; charset=utf-8")
