from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string


class RenewalReminderEmailError(Exception):
    pass


def send_renewal_reminder_email(notification, order, days):
    recipient = (notification.user.email or "").strip()
    if not recipient:
        raise RenewalReminderEmailError("The customer account has no email address.")

    language_code = "pl" if notification.user.preferred_language.startswith("pl") else "en"
    context = {
        "notification": notification,
        "order": order,
        "days": days,
        "language_code": language_code,
        "renewal_url": f"{settings.SITE_BASE_URL.rstrip('/')}{notification.action_url}",
    }
    subject = notification.localized_title(language_code)
    message = EmailMultiAlternatives(
        subject=subject,
        body=render_to_string("emails/plan_renewal_reminder.txt", context),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[recipient],
    )
    message.attach_alternative(
        render_to_string("emails/plan_renewal_reminder.html", context),
        "text/html",
    )
    if message.send() != 1:
        raise RenewalReminderEmailError("The renewal reminder was not accepted for delivery.")
