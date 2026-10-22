"""Two front doors: /login/ for lab staff, /dynamic/login/ for Dynamic APAC admins."""

from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.views import LoginView
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils import timezone

from .roles import is_dynamic_admin


class LabLoginForm(AuthenticationForm):
    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if is_dynamic_admin(user):
            raise forms.ValidationError(
                "This is a Dynamic APAC admin account — please use the admin sign-in.",
                code="use_admin_login",
            )
        if hasattr(user, "client_profile"):
            raise forms.ValidationError(
                "This is a client account — please sign in through the client portal.",
                code="use_client_login",
            )


class AdminLoginForm(AuthenticationForm):
    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not is_dynamic_admin(user):
            raise forms.ValidationError(
                "This sign-in is for Dynamic APAC administrators only. Lab staff sign in at the lab sign-in page.",
                code="not_dynamic_admin",
            )


class LabLoginView(LoginView):
    template_name = "registration/login.html"
    authentication_form = LabLoginForm


class AdminLoginView(LoginView):
    template_name = "registration/admin_login.html"
    authentication_form = AdminLoginForm
    next_page = reverse_lazy("dynamic_console")

    def get_default_redirect_url(self):
        return str(self.next_page)


def dynamic_admin_required(view):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f"{reverse_lazy('dynamic_login')}?next={request.path}")
        if not is_dynamic_admin(request.user):
            raise PermissionDenied
        return view(request, *args, **kwargs)

    wrapper.__name__ = view.__name__
    return wrapper


@dynamic_admin_required
def admin_console(request):
    from reports.models import Certificate
    from samples.models import Sample

    User = get_user_model()
    today = timezone.localdate()
    month_start = today.replace(day=1)
    samples = Sample.objects.all()
    stats = {
        "samples_total": samples.count(),
        "samples_month": samples.filter(date_received__gte=month_start).count(),
        "samples_open": samples.exclude(status__in=[Sample.STATUS_COMPLETE, Sample.STATUS_DISPOSED]).count(),
        "certs_total": Certificate.objects.count(),
        "certs_month": Certificate.objects.filter(issued_at__date__gte=month_start).count(),
    }
    staff = (
        User.objects.filter(client_profile__isnull=True)
        .prefetch_related("groups")
        .order_by("-is_superuser", "username")
    )
    people = [
        {"user": u, "groups": [g.name for g in u.groups.all()], "admin": is_dynamic_admin(u)} for u in staff
    ]
    recent = Sample.objects.select_related("fuel_type").order_by("-created_at")[:8]
    feed = {
        "recipient": getattr(settings, "DMS_NOTIFICATION_EMAIL", ""),
        "smtp_ready": bool(getattr(settings, "EMAIL_HOST", "")) and "console" not in settings.EMAIL_BACKEND,
    }
    return render(
        request,
        "accounts/admin_console.html",
        {"stats": stats, "people": people, "recent": recent, "feed": feed},
    )


def csrf_failure(request, reason=""):
    """Friendlier than Django's bare 403 page.

    Almost always caused by a stale form: a double-submitted sign-in, or a
    page left open across a sign-in/sign-out. If you're already signed in,
    just carry on; otherwise send you back to the page with a fresh form.
    """
    from django.contrib import messages
    from django.http import HttpResponseForbidden
    from django.utils.http import url_has_allowed_host_and_scheme

    login_paths = {str(reverse_lazy("login")), str(reverse_lazy("dynamic_login")), "/portal/login/"}
    if request.path in login_paths and request.user.is_authenticated:
        if request.path == str(reverse_lazy("dynamic_login")):
            return redirect("dynamic_console")
        return redirect("accounts:portal_home" if request.path == "/portal/login/" else "dashboard:home")
    if request.method == "POST":
        try:
            messages.warning(request, "That form had expired — please try again.")
        except Exception:
            pass
        back = request.path
        if url_has_allowed_host_and_scheme(back, allowed_hosts={request.get_host()}):
            return redirect(back)
    return HttpResponseForbidden("This form expired. Go back, refresh the page and try again.")
