from django.urls import path

from .views import AccountCloseView, ProfilePasswordChangeView, ProfileView

app_name = "accounts"

urlpatterns = [
    path("profile/", ProfileView.as_view(), name="profile"),
    path("profile/password/", ProfilePasswordChangeView.as_view(), name="profile-password"),
    path("profile/close-account/", AccountCloseView.as_view(), name="close-account"),
]
