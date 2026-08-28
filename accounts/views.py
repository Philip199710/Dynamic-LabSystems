from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import get_object_or_404, redirect, render

from labtests.forms import ResultEntryForm
from labtests.models import SampleTest
from reports.views import render_coa_pdf
from samples.models import Sample

from .emails import (
    send_client_approved_notification,
    send_client_registration_notification,
    send_sample_requested_notification,
)
from .forms import ClientRegistrationForm, ClientSampleRequestForm
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
def client_portal_request_sample(request, profile):
    if request.method == "POST":
        form = ClientSampleRequestForm(request.POST)
        if form.is_valid():
            sample = form.save(commit=False)
            sample.client = profile.client
            sample.status = Sample.STATUS_REQUESTED
            sample.save()
            sample.log(request.user, "Sample requested via client portal", notes=f"Source: {sample.source}")
            send_sample_requested_notification(sample, request=request)
            messages.success(
                request,
                f"Request submitted — {sample.sample_id} will show up once a Lab Manager confirms intake.",
            )
            return redirect("accounts:portal_sample_detail", pk=sample.pk)
    else:
        form = ClientSampleRequestForm()
    return render(request, "accounts/portal_request_sample.html", {"profile": profile, "form": form})


@client_portal_required
def client_portal_sample_detail(request, profile, pk):
    sample = get_object_or_404(
        Sample.objects.select_related("fuel_type"), pk=pk, client=profile.client
    )
    tests = sample.tests.select_related("test_method").all()
    locked = hasattr(sample, "certificate")
    rows = [
        {
            "sample_test": t,
            "test_method": t.test_method,
            "result": t.result,
            "verdict": t.result.pass_fail if t.result else None,
        }
        for t in tests
    ]
    return render(
        request,
        "accounts/portal_sample_detail.html",
        {"profile": profile, "sample": sample, "rows": rows, "locked": locked},
    )


@client_portal_required
def client_portal_enter_result(request, profile, pk):
    """A client recording their own test result for one of their samples.

    No lab review gate on the value itself — Dynamic LabSystems chose to
    let clients enter and finalize their own readings (mirrors staff's
    enter_result). What stays staff-only is issuing the certificate
    (reports.views.issue_certificate): once that's happened, results here
    are locked, so a client can't edit the numbers a certificate already
    went out on. TestResult.record() logs every entry to the sample's
    chain-of-custody with the acting user, so a client-entered value is
    always visibly attributed to the client account that entered it.
    """
    sample_test = get_object_or_404(
        SampleTest.objects.select_related("sample", "test_method"),
        pk=pk,
        sample__client=profile.client,
    )
    if hasattr(sample_test.sample, "certificate"):
        messages.error(request, "This sample's certificate has already been issued — results are locked.")
        return redirect("accounts:portal_sample_detail", pk=sample_test.sample_id)

    existing = sample_test.result
    if request.method == "POST":
        form = ResultEntryForm(request.POST, instance=existing)
        if form.is_valid():
            result = form.save(commit=False)
            result.sample_test = sample_test
            result.entered_by = request.user
            result.record(request.user)
            verdict = result.pass_fail
            if verdict is False:
                messages.warning(request, f"Result recorded — OUT OF SPEC for {sample_test.test_method.name}.")
            else:
                messages.success(request, f"Result recorded for {sample_test.test_method.name}.")
            return redirect("accounts:portal_sample_detail", pk=sample_test.sample_id)
    else:
        form = ResultEntryForm(instance=existing)
    return render(
        request, "accounts/portal_enter_result.html", {"profile": profile, "form": form, "sample_test": sample_test}
    )


@client_portal_required
def client_portal_coa_pdf(request, profile, pk):
    sample = get_object_or_404(Sample, pk=pk, client=profile.client)
    if not hasattr(sample, "certificate"):
        messages.info(request, "This sample's certificate hasn't been issued yet.")
        return redirect("accounts:portal_sample_detail", pk=pk)
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
