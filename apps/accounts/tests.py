from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from unittest.mock import patch

from apps.accounts.models import UserPlanTier
from apps.billing.models import BillingSubscription


User = get_user_model()


class RegistrationFlowTests(TestCase):
    def test_register_creates_user_without_email_verification(self):
        response = self.client.post(
            reverse("register"),
            {
                "username": "newclient",
                "company_name": "Acme Sp. z o.o.",
                "email": "client@example.com",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
        )

        self.assertRedirects(response, reverse("login"))
        user = User.objects.get(username="newclient")
        self.assertEqual(user.company_name, "Acme Sp. z o.o.")
        self.assertEqual(user.email, "client@example.com")
        self.assertIsNotNone(user.date_joined)

    def test_last_login_is_updated_after_first_sign_in(self):
        User.objects.create_user(
            username="newclient",
            email="client@example.com",
            company_name="Acme Sp. z o.o.",
            password="StrongPass123!",
        )

        response = self.client.post(
            reverse("login"),
            {
                "username": "newclient",
                "password": "StrongPass123!",
            },
        )

        self.assertEqual(response.status_code, 302)
        user = User.objects.get(username="newclient")
        self.assertIsNotNone(user.last_login)

    def test_profile_shows_close_account_action(self):
        user = User.objects.create_user(
            username="client",
            email="client@example.com",
            password="StrongPass123!",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("accounts:profile"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("accounts:close-account"))
        self.assertContains(response, "Close account")

    def test_close_account_deletes_basic_user(self):
        user = User.objects.create_user(
            username="client-delete",
            email="client-delete@example.com",
            password="StrongPass123!",
        )
        self.client.force_login(user)

        response = self.client.post(reverse("accounts:close-account"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("login"))
        self.assertFalse(User.objects.filter(pk=user.pk).exists())

    @override_settings(STRIPE_SECRET_KEY="sk_test_dummy")
    @patch("apps.accounts.views.stripe.Subscription.delete")
    def test_close_account_cancels_active_subscription_before_deleting_user(self, mock_subscription_delete):
        user = User.objects.create_user(
            username="paid-delete",
            email="paid-delete@example.com",
            password="StrongPass123!",
            plan_tier=UserPlanTier.PLUS,
        )
        BillingSubscription.objects.create(
            user=user,
            tier=UserPlanTier.PLUS,
            stripe_customer_id="cus_test_123",
            stripe_subscription_id="sub_test_123",
            status="active",
        )
        self.client.force_login(user)

        response = self.client.post(reverse("accounts:close-account"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("login"))
        mock_subscription_delete.assert_called_once_with("sub_test_123")
        self.assertFalse(User.objects.filter(pk=user.pk).exists())
