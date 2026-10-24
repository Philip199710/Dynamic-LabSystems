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
        membership = getattr(user, "lab_membership", None)
        if membership is None:
            raise forms.ValidationError(
                "This login isn't assigned to a lab yet. Ask Dynamic APAC to set it up.", code="no_lab"
            )
        if not membership.lab.licence_valid:
            raise forms.ValidationError(
                f"{membership.lab.name}'s licence is not active. Contact Dynamic APAC.", code="licence"
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

    def form_valid(self, form):
        from labs.devices import check_device, client_ip, is_new_network, record_event, set_device_cookie
        from labs.models import Device, LoginEvent

        user = form.get_user()
        lab = user.lab_membership.lab
        device, new_raw = check_device(self.request, user, lab)
        if device.status != Device.STATUS_APPROVED:
            revoked = device.status == Device.STATUS_REVOKED
            record_event(
                self.request, user=user, lab=lab, device=device,
                outcome=LoginEvent.OUTCOME_BLOCKED if revoked else LoginEvent.OUTCOME_PENDING,
                detail="Revoked PC" if revoked else "New PC",
            )
            response = render(self.request, "labs/device_pending.html", {"lab": lab, "device": device, "revoked": revoked, "login_user": user})
            return set_device_cookie(response, new_raw) if new_raw else response
        new_net = is_new_network(user, client_ip(self.request))
        response = super().form_valid(form)
        record_event(self.request, user=user, lab=lab, device=device, outcome=LoginEvent.OUTCOME_OK, new_network=new_net)
        return set_device_cookie(response, new_raw) if new_raw else response

    def form_invalid(self, form):
        _record_failure(self.request, form)
        return super().form_invalid(form)


def _record_failure(request, form):
    from labs.devices import record_event
    from labs.models import LoginEvent

    username = (request.POST.get("username") or "")[:150]
    if not username:
        return
    User = get_user_model()
    user = User.objects.filter(username=username).first()
    lab = getattr(getattr(user, "lab_membership", None), "lab", None) if user else None
    errors = " ".join(str(e) for e in form.non_field_errors())[:200]
    record_event(request, user=user, username=username, lab=lab, outcome=LoginEvent.OUTCOME_FAILED, detail=errors)


class AdminLoginView(LoginView):
    template_name = "registration/admin_login.html"
    authentication_form = AdminLoginForm
    next_page = reverse_lazy("dynamic_console")

    def get_default_redirect_url(self):
        return str(self.next_page)

    def form_valid(self, form):
        from labs.devices import client_ip, is_new_network, record_event
        from labs.models import LoginEvent

        user = form.get_user()
        new_net = is_new_network(user, client_ip(self.request))
        response = super().form_valid(form)
        record_event(self.request, user=user, outcome=LoginEvent.OUTCOME_OK, detail="Dynamic admin", new_network=new_net)
        return response

    def form_invalid(self, form):
        _record_failure(self.request, form)
        return super().form_invalid(form)


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
    from django.db.models import Count, Q

    from labs.models import Device, Lab, LoginEvent

    labs = Lab.objects.annotate(
        logins=Count("members", filter=Q(members__user__is_active=True), distinct=True),
        samples_n=Count("samples", distinct=True),
    )
    pending_devices = Device.objects.filter(status=Device.STATUS_PENDING, user__is_active=True).select_related(
        "user", "user__lab_membership__lab"
    )[:20]
    week_ago = timezone.now() - timezone.timedelta(days=7)
    flagged = LoginEvent.objects.filter(created_at__gte=week_ago).filter(
        Q(new_network=True) | Q(outcome=LoginEvent.OUTCOME_BLOCKED)
    ).select_related("lab")[:10]
    return render(
        request,
        "accounts/admin_console.html",
        {"stats": stats, "people": people, "recent": recent, "feed": feed,
         "labs": labs, "pending_devices": pending_devices, "flagged": flagged},
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
