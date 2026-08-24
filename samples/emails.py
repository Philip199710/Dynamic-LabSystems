import logging

from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse

logger = logging.getLogger(__name__)


def send_sample_registered_notification(sample, request=None):
    """Email a record of a newly registered sample to SAMPLE_NOTIFICATION_EMAIL.

    Best-effort: any failure (bad/missing SMTP credentials, network issue) is
    logged and swallowed rather than raised, so a mail problem never blocks
    sample registration itself.
    """
    recipient = getattr(settings, "SAMPLE_NOTIFICATION_EMAIL", "")
    if not recipient:
        return

    detail_path = reverse("samples:detail", args=[sample.pk])
    detail_url = request.build_absolute_uri(detail_path) if request else detail_path

    subject = f"[{settings.SITE_NAME}] New sample registered: {sample.sample_id}"
    body = (
        f"A new sample was registered in {settings.SITE_NAME}.\n\n"
        f"Sample ID:        {sample.sample_id}\n"
        f"Fuel type:        {sample.fuel_type.name}\n"
        f"Source:           {sample.source}\n"
        f"Date received:    {sample.date_received}\n"
        f"Storage location: {sample.storage_location or '—'}\n"
        f"Received by:      {sample.received_by.get_username() if sample.received_by else '—'}\n"
        f"Notes:            {sample.notes or '—'}\n\n"
        f"View sample: {detail_url}\n\n"
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
        logger.exception("Failed to send sample-registered notification for %s", sample.sample_id)
