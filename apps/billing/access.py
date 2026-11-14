"""Read-only access decisions. Expiry never depends on a customer page visit."""
from datetime import timedelta

from django.db.models import Q
from django.utils import timezone
from apps.accounts.models import UserPlanAccessStatus, UserPlanTier
from .models import AnnualPlanPaymentMethod, BillingSubscription, ManualPlanOrder


PLAN_RANKS = {
    UserPlanTier.BASIC: 0,
    UserPlanTier.PLUS: 1,
    UserPlanTier.PRO: 2,
}


def eligible_manual_orders(user):
    now = timezone.now()
    return ManualPlanOrder.objects.filter(user=user, access_until__gt=now).filter(
        Q(access_starts_at__isnull=True) | Q(access_starts_at__lte=now)
    ).filter(
        Q(status="paid")
        | Q(
            status="awaiting_payment",
            payment_method=AnnualPlanPaymentMethod.BANK_TRANSFER,
            payment_due_at__gt=now,
            renewal_of__isnull=True,
        )
    )


def renewable_manual_order(user, tier=None, *, at=None, window_days=30):
    """Return the paid period that may be renewed early, if it has no successor."""
    at = at or timezone.now()
    queryset = ManualPlanOrder.objects.filter(
        user=user,
        status="paid",
        access_until__gt=at,
        access_until__lte=at + timedelta(days=window_days),
    )
    if tier:
        queryset = queryset.filter(tier=tier)
    queryset = queryset.exclude(
        renewal_orders__status__in=["awaiting_payment", "paid"],
    )
    return queryset.order_by("-access_until", "-created_at").first()


def upgradeable_manual_order(user, target_tier=None, *, at=None):
    """Return the current paid manual period when a higher tier can replace it."""
    at = at or timezone.now()
    order = ManualPlanOrder.objects.filter(
        user=user,
        status="paid",
        access_until__gt=at,
    ).filter(
        Q(access_starts_at__isnull=True) | Q(access_starts_at__lte=at)
    ).exclude(
        renewal_orders__status__in=["awaiting_payment", "paid"],
    ).exclude(
        upgrade_orders__status__in=["awaiting_payment", "paid"],
    ).order_by("-access_until", "-created_at").first()
    if not order or PLAN_RANKS.get(order.tier, -1) >= PLAN_RANKS[UserPlanTier.PRO]:
        return None
    if target_tier and PLAN_RANKS.get(target_tier, -1) <= PLAN_RANKS.get(order.tier, -1):
        return None
    return order


def effective_tier(user):
    manual = eligible_manual_orders(user).order_by("-created_at").first()
    if manual:
        return manual.tier
    subscription = BillingSubscription.objects.filter(user=user).first()
    if subscription:
        if subscription.status in {"active", "trialing"} and subscription.current_period_end and subscription.current_period_end > timezone.now():
            return subscription.tier
        return user.plan_tier
    if ManualPlanOrder.objects.filter(user=user).exists():
        return user.plan_tier
    return user.plan_tier


def reconcile_access(user):
    from .services import activate_paid_plan, expire_paid_access
    tier = effective_tier(user)
    if has_publication_access(user):
        if tier != user.plan_tier or user.plan_access_status != UserPlanAccessStatus.ACTIVE:
            activate_paid_plan(user, tier)
    elif user.plan_access_status != UserPlanAccessStatus.EXPIRED:
        expire_paid_access(user)
    return tier


def publication_users():
    """Paid publication, including the existing manual payment grace period."""
    from django.contrib.auth import get_user_model
    now = timezone.now()
    stripe_users = BillingSubscription.objects.filter(status__in=["active", "trialing"], current_period_end__gt=now).values("user_id")
    manual_users = ManualPlanOrder.objects.filter(access_until__gt=now).filter(
        Q(access_starts_at__isnull=True) | Q(access_starts_at__lte=now)
    ).filter(
        Q(status="paid")
        | Q(
            status="awaiting_payment",
            payment_method=AnnualPlanPaymentMethod.BANK_TRANSFER,
            payment_due_at__gt=now,
            renewal_of__isnull=True,
        )
    ).values("user_id")
    return get_user_model().objects.filter(is_active=True).filter(
        Q(pk__in=stripe_users) | Q(pk__in=manual_users) | Q(is_superuser=True)
    ).distinct()


def has_publication_access(user):
    return publication_users().filter(pk=user.pk).exists()
