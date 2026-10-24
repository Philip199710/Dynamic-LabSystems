"""Approved-device sign-in, and the sign-in log with location."""

import ipaddress
import json
import logging
import re
import threading
import urllib.request

from django.conf import settings
from django.core.mail import EmailMessage
from django.db import close_old_connections, transaction
from django.utils import timezone

from .models import Device, LoginEvent, hash_key, new_device_key

logger = logging.getLogger(__name__)

DEVICE_COOKIE = "dl_device"
DEVICE_COOKIE_AGE = 5 * 365 * 24 * 3600


def client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    ip = forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR", "")
    try:
        ipaddress.ip_address(ip)
        return ip
    except ValueError:
        return None


def device_label(user_agent):
    ua = user_agent or ""
    os_name = next(
        (name for pat, name in [
            (r"Windows NT 10", "Windows"), (r"Windows", "Windows"), (r"Android", "Android"),
            (r"iPhone|iPad", "iOS"), (r"Mac OS X", "macOS"), (r"Linux", "Linux"),
        ] if re.search(pat, ua)),
        "Unknown OS",
    )
    browser = next(
        (name for pat, name in [
            (r"Edg/", "Edge"), (r"OPR/|Opera", "Opera"), (r"Chrome/", "Chrome"),
            (r"Firefox/", "Firefox"), (r"Safari/", "Safari"),
        ] if re.search(pat, ua)),
        "Browser",
    )
    return f"{browser} on {os_name}"


def device_for_request(request, user):
    raw = request.COOKIES.get(DEVICE_COOKIE)
    if not raw:
        return None
    return Device.objects.filter(user=user, key_hash=hash_key(raw)).first()


def network_of(ip):
    try:
        addr = ipaddress.ip_address(ip)
    except (TypeError, ValueError):
        return None
    prefix = 24 if addr.version == 4 else 48
    return str(ipaddress.ip_network(f"{ip}/{prefix}", strict=False))


def is_new_network(user, ip):
    net = network_of(ip)
    if net is None:
        return False
    seen = LoginEvent.objects.filter(user=user, outcome=LoginEvent.OUTCOME_OK).exclude(ip__isnull=True)
    if not seen.exists():
        return False  # first ever sign-in sets the baseline
    return not any(network_of(e.ip) == net for e in seen.only("ip")[:500])


def lookup_place(ip):
    """Best-effort city/country for an IP (ipinfo.io, no key). Never raises."""
    if not getattr(settings, "GEOIP_LOOKUP", True) or not ip:
        return "", ""
    try:
        if ipaddress.ip_address(ip).is_private:
            return "", ""
        with urllib.request.urlopen(f"https://ipinfo.io/{ip}/json", timeout=3) as resp:
            data = json.loads(resp.read().decode())
        return data.get("city", "")[:100], data.get("country", "")[:100]
    except Exception:
        return "", ""


def _notify(subject, body):
    recipient = getattr(settings, "DMS_NOTIFICATION_EMAIL", "")
    if not recipient:
        return

    def send():
        try:
            EmailMessage(subject, body, settings.DEFAULT_FROM_EMAIL, [recipient],
                         headers={"X-Dynamic-Event": "security"}).send()
        except Exception:
            logger.exception("Security email failed: %s", subject)

    if getattr(settings, "DMS_EMAIL_ASYNC", True):
        threading.Thread(target=send, daemon=True).start()
    else:
        send()


def record_event(request, *, user=None, username="", lab=None, device=None, outcome, detail="", new_network=False):
    ip = client_ip(request)
    event = LoginEvent.objects.create(
        user=user, username=username or (user.get_username() if user else ""), lab=lab, device=device,
        outcome=outcome, detail=detail[:200], ip=ip, user_agent=request.META.get("HTTP_USER_AGENT", "")[:300],
        new_network=new_network,
    )

    def fill_place():
        city, country = lookup_place(ip)
        if city or country:
            LoginEvent.objects.filter(pk=event.pk).update(city=city, country=country)
        if new_network:
            e = LoginEvent.objects.select_related("lab").get(pk=event.pk)
            _notify(
                f"[Dynamic LabSystems] Sign-in from a new network: {e.username} ({e.lab.code if e.lab else '-'})",
                f"{e.username} signed in from a network not seen before for this login.\n\n"
                f"Lab:      {e.lab.name if e.lab else '-'}\nIP:       {e.ip}\nLocation: {e.place or 'unknown'}\n"
                f"Device:   {device.label if device else '-'}\nTime:     {timezone.localtime(e.created_at):%Y-%m-%d %H:%M}\n\n"
                f"If this login is being shared, revoke the device in the Dynamic admin console.",
            )

    def run():
        try:
            fill_place()
        finally:
            if getattr(settings, "DMS_EMAIL_ASYNC", True):
                close_old_connections()

    if getattr(settings, "DMS_EMAIL_ASYNC", True):
        transaction.on_commit(lambda: threading.Thread(target=run, daemon=True).start())
    else:
        transaction.on_commit(run)
    return event


def check_device(request, user, lab):
    """Return (device, raw_key_to_set_or_None). Approves automatically when the
    lab allows the login's first PC; otherwise leaves it pending."""
    raw = request.COOKIES.get(DEVICE_COOKIE)
    new_raw = None
    if not raw:
        raw = new_raw = new_device_key()
    ua = request.META.get("HTTP_USER_AGENT", "")
    ip = client_ip(request)
    device, created = Device.objects.get_or_create(
        user=user, key_hash=hash_key(raw), defaults={"label": device_label(ua), "first_ip": ip}
    )
    if device.status == Device.STATUS_PENDING:
        approved = user.devices.filter(status=Device.STATUS_APPROVED).count()
        if lab.auto_approve_first_device and approved == 0 and not user.devices.filter(status=Device.STATUS_REVOKED).exists():
            device.status = Device.STATUS_APPROVED
            device.decided_at = timezone.now()
            device.save(update_fields=["status", "decided_at"])
        elif created:
            _notify(
                f"[Dynamic LabSystems] New PC waiting for approval: {user.get_username()} ({lab.code})",
                f"{user.get_full_name() or user.get_username()} ({lab.name}) tried to sign in on a new PC.\n\n"
                f"Device: {device.label}\nIP:     {ip}\n\n"
                f"Approve or refuse it in the Dynamic admin console → Labs → {lab.name}.",
            )
    device.last_ip = ip
    device.last_seen = timezone.now()
    device.save(update_fields=["last_ip", "last_seen"])
    return device, new_raw


def set_device_cookie(response, raw):
    response.set_cookie(
        DEVICE_COOKIE, raw, max_age=DEVICE_COOKIE_AGE, httponly=True, samesite="Lax",
        secure=not settings.DEBUG,
    )
    return response
