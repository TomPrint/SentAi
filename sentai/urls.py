from django.conf import settings
from django.conf.urls.i18n import i18n_patterns
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.i18n import set_language
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

from apps.accounts.views import RegisterView
from apps.companies.views import SiteLLMsTextView

admin.site.site_header = "SentAi Administration"
admin.site.site_title = "SentAi Admin"
admin.site.index_title = "Platform management"

urlpatterns = [
    path("i18n/", include("django.conf.urls.i18n")),
    # OpenAPI schema + interactive docs (GET only by design)
    path("openapi.json", SpectacularAPIView.as_view(), name="openapi-schema"),
    path("api/schema/swagger-ui/", SpectacularSwaggerView.as_view(url_name="openapi-schema"), name="api-schema-swagger-ui"),
    path("api/schema/redoc/", SpectacularRedocView.as_view(url_name="openapi-schema"), name="api-schema-redoc"),
    # Site-wide llms.txt for LLM crawlers
    path("llms.txt", SiteLLMsTextView.as_view(), name="site-llms-txt"),
    path(
        "api/auth/",
        include(("apps.accounts.api_urls", "accounts_api"), namespace="accounts_api"),
    ),
    path(
        "api/",
        include(("apps.companies.api_urls", "companies_api"), namespace="companies_api"),
    ),
]

urlpatterns += i18n_patterns(
    path("accounts/register/", RegisterView.as_view(), name="register"),
    path("accounts/", include("django.contrib.auth.urls")),
        path("accounts/", include(("apps.accounts.urls", "accounts"), namespace="accounts")),
    path("set-language/", set_language, name="set_language_localized"),
    path("admin/", admin.site.urls),
    path("", include(("apps.dashboard.urls", "dashboard"), namespace="dashboard")),
    prefix_default_language=False,
)

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
