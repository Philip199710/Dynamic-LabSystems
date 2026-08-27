import logging

from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse

logger = logging.getLogger(__name__)


def send_client_registration_notification(profile, request=None):
    """Tell staff a new client-portal account is waiting for approval.

    Best-effort, same pattern as samples.emails — a mail failure never blocks
    the registration itself.
    """
    recipient = getattr(settings, "SAMPLE_NOTIFICATION_EMAIL", "")
    if not recipient:
        return

    pending_path = reverse("accounts:pending_clients")
    pending_url = request.build_absolute_uri(pending_path) if request else pending_path

    subject = f"[{settings.SITE_NAME}] New client portal account pending approval"
    body = (
        f"A new client portal account is waiting for approval in {settings.SITE_NAME}.\n\n"
        f"Company: {profile.client.name}\n"
        f"Contact: {profile.user.get_full_name() or profile.user.get_username()}\n"
        f"Email:   {profile.user.email}\n\n"
        f"Review: {pending_url}\n\n"
        f"This is an automated notification — do not reply to this email."
    )
    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient],
            fail_silently=False,
        )
    except Exception:
        logger.exception("Failed to send client-registration notification for %s", profile.client.name)


def send_sample_requested_notification(sample, request=None):
    """Tell staff a client submitted a new sample request awaiting intake."""
    recipient = getattr(settings, "SAMPLE_NOTIFICATION_EMAIL", "")
    if not recipient:
        return

    detail_path = reverse("samples:detail", args=[sample.pk])
    detail_url = request.build_absolute_uri(detail_path) if request else detail_path

    subject = f"[{settings.SITE_NAME}] Client sample request: {sample.sample_id}"
    body = (
        f"{sample.client.name} submitted a new sample through the client portal in {settings.SITE_NAME}.\n\n"
        f"Sample ID:  {sample.sample_id}\n"
        f"Fuel type:  {sample.fuel_type.name}\n"
        f"Source:     {sample.source}\n"
        f"Notes:      {sample.notes or '—'}\n\n"
        f"It won't enter the testing workflow until a staff member confirms intake.\n"
        f"Review: {detail_url}\n\n"
        f"This is an automated notification — do not reply to this email."
    )
    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient],
            fail_silently=False,
        )
    except Exception:
        logger.exception("Failed to send sample-requested notification for %s", sample.sample_id)


def send_client_approved_notification(profile, request=None):
    """Tell the client their portal account is now active."""
    if not profile.user.email:
        return

    login_path = reverse("accounts:client_login")
    login_url = request.build_absolute_uri(login_path) if request else login_path

    subject = f"[{settings.SITE_NAME}] Your client portal account is approved"
    body = (
        f"Your {settings.SITE_NAME} client portal account for {profile.client.name} has been approved.\n\n"
        f"Sign in: {login_url}\n"
        f"Username: {profile.user.email}\n\n"
        f"This is an automated notification — do not reply to this email."
    )
    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[profile.user.email],
            fail_silently=False,
        )
    except Exception:
        logger.exception("Failed to send client-approved notification to %s", profile.user.email)
