from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import get_object_or_404, redirect, render

from reports.views import render_coa_pdf
from samples.models import Sample

from .emails import send_client_approved_notification, send_client_registration_notification
from .forms import ClientRegistrationForm
from .models import ClientProfile


def client_portal_required(view_func):
    """Like @login_required, but also requires an approved ClientProfile.

    A logged-in client without one (not yet approved, or a staff account
    with no profile at all) gets the pending/no-access page instead of a
    crash or a 403 — see templates/accounts/portal_pending.html.
    """

    @wraps(view_func)
    @login_required
    def wrapped(request, *args, **kwargs):
        profile = getattr(request.user, "client_profile", None)
        if profile is None or not profile.is_approved:
            return render(request, "accounts/portal_pending.html", {"profile": profile})
        return view_func(request, profile, *args, **kwargs)

    return wrapped


def client_register(request):
    if request.method == "POST":
        form = ClientRegistrationForm(request.POST)
        if form.is_valid():
            profile = form.save()
            send_client_registration_notification(profile, request=request)
            messages.success(
                request,
                "Thanks — your account has been created. A Lab Manager will review and approve it, "
                "and you'll get an email once you can sign in.",
            )
            return redirect("accounts:client_login")
    else:
        form = ClientRegistrationForm()
    return render(request, "accounts/register.html", {"form": form})


@client_portal_required
def client_portal_home(request, profile):
    samples = profile.client.samples.select_related("fuel_type").order_by("-created_at")
    return render(request, "accounts/portal_home.html", {"profile": profile, "samples": samples})


@client_portal_required
def client_portal_sample_detail(request, profile, pk):
    sample = get_object_or_404(
        Sample.objects.select_related("fuel_type"), pk=pk, client=profile.client
    )
    tests = sample.tests.select_related("test_method").all()
    rows = [
        {
            "test_method": t.test_method,
            "result": t.result,
            "verdict": t.result.pass_fail if t.result else None,
        }
        for t in tests
    ]
    return render(
        request,
        "accounts/portal_sample_detail.html",
        {"profile": profile, "sample": sample, "rows": rows},
    )


@client_portal_required
def client_portal_coa_pdf(request, profile, pk):
    sample = get_object_or_404(Sample, pk=pk, client=profile.client)
    return render_coa_pdf(sample)


@permission_required("accounts.change_clientprofile", raise_exception=True)
def pending_clients(request):
    pending = ClientProfile.objects.filter(is_approved=False).select_related("user", "client")
    return render(request, "accounts/pending_clients.html", {"pending": pending})


@permission_required("accounts.change_clientprofile", raise_exception=True)
def approve_client(request, pk):
    profile = get_object_or_404(ClientProfile, pk=pk)
    if request.method == "POST":
        profile.approve(request.user)
        send_client_approved_notification(profile, request=request)
        messages.success(request, f"Approved {profile.user.get_username()} ({profile.client.name}).")
    return redirect("accounts:pending_clients")
