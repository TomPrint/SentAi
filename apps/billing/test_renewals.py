from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User, UserPlanTier
from apps.companies.models import Organization, VerificationStatus
from apps.dashboard.views import create_manual_plan_order
from apps.notifications.models import CustomerNotification
from apps.notifications.services import scan_customer_notifications

from .access import has_publication_access
from .models import (
    AnnualPlanPaymentMethod,
    BillingPlanPrice,
    BillingProfile,
    ManualPlanOrder,
    ManualPlanOrderStatus,
)
from .services import fulfill_blik_checkout


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    SITE_BASE_URL="https://xoaila.example",
    SUBSCRIPTION_BILLING_ENABLED=False,
    BLIK_PAYMENTS_ENABLED=True,
    STRIPE_SECRET_KEY="sk_test_renewal",
)
class AnnualPlanRenewalTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="renewal-customer",
            email="registered@example.com",
            password="Strong-password-123!",
            preferred_language="pl",
            plan_tier=UserPlanTier.PLUS,
        )
        BillingProfile.objects.create(
            user=self.user,
            company_name="Renewal Sp. z o.o.",
            tax_id="PL5260250995",
            street="Prosta 1",
            postal_code="00-001",
            city="Warszawa",
            country="PL",
            invoice_email="invoices@example.com",
        )
        BillingPlanPrice.objects.create(
            tier=UserPlanTier.BASIC,
            currency="pln",
            amount=15000,
            stripe_price_id="price_basic_renewal",
        )
        BillingPlanPrice.objects.create(
            tier=UserPlanTier.PLUS,
            currency="pln",
            amount=20000,
            stripe_price_id="price_plus_renewal",
        )
        BillingPlanPrice.objects.create(
            tier=UserPlanTier.PRO,
            currency="pln",
            amount=40000,
            stripe_price_id="price_pro_renewal",
        )
        self.now = timezone.now().replace(microsecond=0)
        self.current = ManualPlanOrder.objects.create(
            user=self.user,
            tier=UserPlanTier.PLUS,
            amount=20000,
            original_amount=20000,
            currency="pln",
            payment_method=AnnualPlanPaymentMethod.BANK_TRANSFER,
            status=ManualPlanOrderStatus.PAID,
            payment_reference="PLUS-CURRENT-RENEWAL",
            payment_due_at=self.now - timedelta(days=350),
            access_starts_at=self.now - timedelta(days=355),
            access_until=self.now + timedelta(days=10),
            paid_at=self.now - timedelta(days=355),
        )

    def test_14_and_5_day_reminders_are_internal_and_emailed_once(self):
        with patch("apps.notifications.services.timezone.now", return_value=self.now):
            scan_customer_notifications(self.user)
            scan_customer_notifications(self.user)

        reminder_14 = CustomerNotification.objects.get(
            reference_key__contains="manual-renewal-14"
        )
        self.assertIsNotNone(reminder_14.email_sent_at)
        self.assertEqual(reminder_14.email_error, "")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.user.email])
        self.assertIn("14", mail.outbox[0].subject)

        five_days_before = self.current.access_until - timedelta(days=5)
        with patch("apps.notifications.services.timezone.now", return_value=five_days_before):
            scan_customer_notifications(self.user)
            scan_customer_notifications(self.user)

        reminder_5 = CustomerNotification.objects.get(
            reference_key__contains="manual-renewal-5"
        )
        self.assertIsNotNone(reminder_5.email_sent_at)
        self.assertEqual(len(mail.outbox), 2)
        self.assertIn("5", mail.outbox[1].subject)

    @override_settings(STRIPE_SECRET_KEY="")
    def test_billing_cron_command_generates_and_emails_the_reminder(self):
        call_command("maintain_billing", stdout=StringIO())

        notification = CustomerNotification.objects.get(
            reference_key__contains="manual-renewal-14"
        )
        self.assertIsNotNone(notification.email_sent_at)
        self.assertEqual(mail.outbox[0].to, [self.user.email])

    def test_bank_transfer_renewal_starts_after_current_period(self):
        renewal = create_manual_plan_order(
            self.user,
            "pln",
            tier=UserPlanTier.PLUS,
            payment_reference="PLUS-NEXT-BANK",
            renewal_of_id=self.current.pk,
        )

        self.assertEqual(renewal.renewal_of, self.current)
        self.assertEqual(renewal.access_starts_at, self.current.access_until)
        self.assertEqual(renewal.access_until, self.current.access_until + timedelta(days=365))
        self.assertEqual(renewal.status, ManualPlanOrderStatus.AWAITING_PAYMENT)

        after_current_period = self.current.access_until + timedelta(seconds=1)
        with patch("apps.billing.access.timezone.now", return_value=after_current_period):
            self.assertFalse(has_publication_access(self.user))

        renewal.status = ManualPlanOrderStatus.PAID
        renewal.paid_at = self.now
        renewal.save(update_fields=["status", "paid_at", "updated_at"])
        with patch("apps.billing.access.timezone.now", return_value=after_current_period):
            self.assertTrue(has_publication_access(self.user))

    def test_immediate_plan_removal_also_cancels_scheduled_renewal(self):
        renewal = create_manual_plan_order(
            self.user,
            "pln",
            tier=UserPlanTier.PLUS,
            payment_reference="PLUS-NEXT-CANCELED",
            renewal_of_id=self.current.pk,
        )
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("dashboard:billing-subscription-cancel"),
            {"termination_acknowledged": "on"},
        )

        self.assertRedirects(response, reverse("dashboard:home"))
        self.current.refresh_from_db()
        renewal.refresh_from_db()
        self.assertEqual(self.current.status, ManualPlanOrderStatus.DISABLED)
        self.assertEqual(renewal.status, ManualPlanOrderStatus.DISABLED)
        self.assertFalse(has_publication_access(self.user))

    def test_blik_renewal_keeps_the_scheduled_period(self):
        renewal = ManualPlanOrder.objects.create(
            user=self.user,
            tier=UserPlanTier.PLUS,
            amount=20000,
            original_amount=20000,
            currency="pln",
            payment_method=AnnualPlanPaymentMethod.BLIK,
            status=ManualPlanOrderStatus.AWAITING_PAYMENT,
            payment_reference="PLUS-NEXT-BLIK",
            payment_due_at=self.now + timedelta(hours=1),
            access_starts_at=self.current.access_until,
            access_until=self.current.access_until + timedelta(days=365),
            renewal_of=self.current,
        )
        session = {
            "id": "cs_test_renewal_blik",
            "mode": "payment",
            "payment_status": "paid",
            "payment_intent": "pi_test_renewal_blik",
            "amount_total": 20000,
            "currency": "pln",
            "metadata": {
                "payment_kind": "blik_annual",
                "annual_order_id": str(renewal.pk),
                "user_id": str(self.user.pk),
                "plan_tier": UserPlanTier.PLUS,
            },
        }

        fulfill_blik_checkout(session)
        renewal.refresh_from_db()

        self.assertEqual(renewal.status, ManualPlanOrderStatus.PAID)
        self.assertEqual(renewal.access_starts_at, self.current.access_until)
        self.assertEqual(renewal.access_until, self.current.access_until + timedelta(days=365))

    def test_bank_transfer_upgrade_replaces_current_plan_for_full_new_year(self):
        previous_end = self.current.access_until
        with patch("apps.dashboard.views.timezone.now", return_value=self.now):
            upgrade = create_manual_plan_order(
                self.user,
                "pln",
                tier=UserPlanTier.PRO,
                payment_reference="PRO-UPGRADE-BANK",
                upgrade_from_id=self.current.pk,
            )

        self.current.refresh_from_db()
        self.user.refresh_from_db()
        self.assertEqual(self.current.status, ManualPlanOrderStatus.DISABLED)
        self.assertEqual(upgrade.upgrade_from, self.current)
        self.assertEqual(upgrade.status, ManualPlanOrderStatus.AWAITING_PAYMENT)
        self.assertEqual(upgrade.amount, 40000)
        self.assertEqual(upgrade.tier, UserPlanTier.PRO)
        self.assertGreater(upgrade.access_until, previous_end)
        self.assertEqual(upgrade.access_starts_at, self.now)
        self.assertEqual(upgrade.access_until, self.now + timedelta(days=365))
        self.assertEqual(upgrade.access_until - upgrade.access_starts_at, timedelta(days=365))
        self.assertEqual(self.user.plan_tier, UserPlanTier.PRO)
        self.assertTrue(has_publication_access(self.user))

    def test_blik_upgrade_keeps_old_plan_until_stripe_confirms_payment(self):
        upgrade = ManualPlanOrder.objects.create(
            user=self.user,
            tier=UserPlanTier.PRO,
            amount=40000,
            original_amount=40000,
            currency="pln",
            payment_method=AnnualPlanPaymentMethod.BLIK,
            status=ManualPlanOrderStatus.AWAITING_PAYMENT,
            payment_reference="PRO-UPGRADE-BLIK",
            payment_due_at=self.now + timedelta(hours=1),
            access_starts_at=self.now,
            access_until=self.now,
            upgrade_from=self.current,
        )
        self.assertEqual(self.current.status, ManualPlanOrderStatus.PAID)
        self.assertTrue(has_publication_access(self.user))

        session = {
            "id": "cs_test_upgrade_blik",
            "mode": "payment",
            "payment_status": "paid",
            "payment_intent": "pi_test_upgrade_blik",
            "amount_total": 40000,
            "currency": "pln",
            "metadata": {
                "payment_kind": "blik_annual",
                "annual_order_id": str(upgrade.pk),
                "user_id": str(self.user.pk),
                "plan_tier": UserPlanTier.PRO,
            },
        }
        with patch("apps.billing.services.timezone.now", return_value=self.now):
            fulfill_blik_checkout(session)

        self.current.refresh_from_db()
        upgrade.refresh_from_db()
        self.assertEqual(self.current.status, ManualPlanOrderStatus.DISABLED)
        self.assertEqual(upgrade.status, ManualPlanOrderStatus.PAID)
        self.assertEqual(upgrade.access_starts_at, self.now)
        self.assertEqual(upgrade.access_until, self.now + timedelta(days=365))

    def test_upgrade_screen_allows_only_higher_tiers(self):
        self.current.tier = UserPlanTier.BASIC
        self.current.save(update_fields=["tier", "updated_at"])
        self.user.plan_tier = UserPlanTier.BASIC
        self.user.save(update_fields=["plan_tier"])
        self.client.force_login(self.user)

        response = self.client.get(reverse("dashboard:plan-update") + "?upgrade=1")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [value for value, _label in response.context["form"].fields["plan_tier"].choices],
            [UserPlanTier.PLUS, UserPlanTier.PRO],
        )
        self.assertContains(response, "full price")

        response = self.client.post(
            reverse("dashboard:plan-update") + "?upgrade=1",
            {"plan_tier": UserPlanTier.PLUS, "billing_currency": "pln", "upgrade": "1"},
        )
        self.assertRedirects(response, reverse("dashboard:plan-payment-method"))
        pending = self.client.session["pending_plan_purchase"]
        self.assertTrue(pending["manual_upgrade"])
        self.assertEqual(pending["upgrade_from_id"], self.current.pk)

    def test_same_or_lower_plan_cannot_be_bought_as_upgrade(self):
        with self.assertRaisesMessage(ValueError, "not available as an upgrade"):
            create_manual_plan_order(
                self.user,
                "pln",
                tier=UserPlanTier.PLUS,
                payment_reference="PLUS-NOT-AN-UPGRADE",
                upgrade_from_id=self.current.pk,
            )

    def test_expiry_hides_publication_but_preserves_company_data(self):
        organization = Organization.objects.create(
            owner=self.user,
            name="Preserved Company",
            public=True,
            allow_ai_indexing=True,
            verification_status=VerificationStatus.HUMAN_ADMIN_VERIFIED,
        )
        url = reverse("companies_api:public-company-md", args=[organization.slug])
        self.assertEqual(self.client.get(url).status_code, 200)

        self.current.access_until = timezone.now() - timedelta(seconds=1)
        self.current.save(update_fields=["access_until", "updated_at"])

        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertTrue(Organization.objects.filter(pk=organization.pk).exists())

    def test_renewal_screen_is_available_only_in_the_last_30_days(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("dashboard:plan-update") + "?renew=1")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Renew plan")

        self.current.access_until = self.now + timedelta(days=31)
        self.current.save(update_fields=["access_until", "updated_at"])
        response = self.client.get(reverse("dashboard:plan-update") + "?renew=1")
        self.assertRedirects(response, reverse("dashboard:billing-portal"))
