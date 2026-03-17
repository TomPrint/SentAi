from django.urls import path

from .views import CurrentUserView, TokenLoginView


app_name = "accounts_api"

urlpatterns = [
    path("login/", TokenLoginView.as_view(), name="login"),
    path("me/", CurrentUserView.as_view(), name="me"),
]
