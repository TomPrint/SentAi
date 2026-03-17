from django.urls import path

from .views import (
    ContentEntryDetailView,
    ContentEntryListCreateView,
    OrganizationDetailView,
    OrganizationListCreateView,
    ProductDetailView,
    ProductListCreateView,
    PublicCompanyJsonLdView,
    PublicCompanyJsonView,
    PublicLLMsTextView,
    SocialProfileDetailView,
    SocialProfileListCreateView,
    TagDetailView,
    TagListCreateView,
)


app_name = "companies_api"

urlpatterns = [
    path("organizations/", OrganizationListCreateView.as_view(), name="organization-list"),
    path("organizations/<int:pk>/", OrganizationDetailView.as_view(), name="organization-detail"),
    path(
        "organizations/<int:organization_pk>/social-profiles/",
        SocialProfileListCreateView.as_view(),
        name="social-profile-list",
    ),
    path(
        "organizations/<int:organization_pk>/social-profiles/<int:pk>/",
        SocialProfileDetailView.as_view(),
        name="social-profile-detail",
    ),
    path(
        "organizations/<int:organization_pk>/tags/",
        TagListCreateView.as_view(),
        name="tag-list",
    ),
    path(
        "organizations/<int:organization_pk>/tags/<int:pk>/",
        TagDetailView.as_view(),
        name="tag-detail",
    ),
    path(
        "organizations/<int:organization_pk>/products/",
        ProductListCreateView.as_view(),
        name="product-list",
    ),
    path(
        "organizations/<int:organization_pk>/products/<int:pk>/",
        ProductDetailView.as_view(),
        name="product-detail",
    ),
    path(
        "organizations/<int:organization_pk>/entries/",
        ContentEntryListCreateView.as_view(),
        name="entry-list",
    ),
    path(
        "organizations/<int:organization_pk>/entries/<int:pk>/",
        ContentEntryDetailView.as_view(),
        name="entry-detail",
    ),
    path("public/<slug:slug>/company.json", PublicCompanyJsonView.as_view(), name="public-company-json"),
    path("public/<slug:slug>/company.jsonld", PublicCompanyJsonLdView.as_view(), name="public-company-jsonld"),
    path("public/<slug:slug>/llms.txt", PublicLLMsTextView.as_view(), name="public-company-llms"),
]
