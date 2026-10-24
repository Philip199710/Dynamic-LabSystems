from django.contrib import messages
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.utils import timezone
from django.utils.functional import SimpleLazyObject

from accounts.roles import is_dynamic_admin

from .context import lab_for_user
from .devices import DEVICE_COOKIE, device_for_request

EXEMPT_PREFIXES = ("/static/", "/media/", "/healthz", "/login/", "/logout/", "/dynamic/login/", "/portal/", "/register/", "/device/")


class LabMiddleware:
    """Sets request.lab, and signs lab staff out if their PC is no longer approved
    or their lab's licence has lapsed."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.lab = SimpleLazyObject(lambda: lab_for_user(request.user, request.session)) if hasattr(request, "user") else None
        user = getattr(request, "user", None)
        if (
            user is not None
            and user.is_authenticated
            and not request.path.startswith(EXEMPT_PREFIXES)
            and not hasattr(user, "client_profile")
            and not is_dynamic_admin(user)
        ):
            reason = self._block_reason(request, user)
            if reason:
                logout(request)
                messages.error(request, reason)
                return redirect("login")
        return self.get_response(request)

    def _block_reason(self, request, user):
        membership = getattr(user, "lab_membership", None)
        if membership is None:
            return "This login isn't assigned to a lab yet. Ask Dynamic APAC to set it up."
        if not membership.lab.licence_valid:
            return f"{membership.lab.name}'s licence is not active. Contact Dynamic APAC."
        device = device_for_request(request, user)
        if device is None:
            return "Please sign in again — logins are now checked against approved PCs."
        if device.status != device.STATUS_APPROVED:
            return "This PC is no longer approved for your login. Sign in again to request approval."
        # Touch last-seen at most every 10 minutes.
        now = timezone.now()
        if not device.last_seen or (now - device.last_seen).total_seconds() > 600:
            device.last_seen = now
            device.save(update_fields=["last_seen"])
        return None
