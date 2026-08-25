from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import get_object_or_404, redirect, render

from catalog.models import TestMethod
from labtests.forms import AssignTestForm
from .emails import send_sample_registered_notification
from .forms import SampleForm
from .models import Sample


@login_required
def sample_list(request):
    status = request.GET.get("status", "")
    samples = Sample.objects.select_related("fuel_type", "received_by").all()
    if status:
        samples = samples.filter(status=status)
    return render(
        request,
        "samples/sample_list.html",
        {"samples": samples, "status_choices": Sample.STATUS_CHOICES, "current_status": status},
    )


@login_required
def sample_create(request):
    if request.method == "POST":
        form = SampleForm(request.POST)
        if form.is_valid():
            sample = form.save(commit=False)
            sample.received_by = request.user
            sample.save()
            sample.log(request.user, "Sample received", notes=f"Source: {sample.source}")
            send_sample_registered_notification(sample, request=request)
            messages.success(request, f"Sample {sample.sample_id} registered.")
            return redirect("samples:detail", pk=sample.pk)
    else:
        form = SampleForm()
    return render(request, "samples/sample_form.html", {"form": form})


@login_required
def sample_detail(request, pk):
    sample = get_object_or_404(Sample.objects.select_related("fuel_type", "received_by"), pk=pk)
    tests = sample.tests.select_related("test_method", "assigned_to").all()
    custody_log = sample.custody_log.select_related("actor").all()
    assign_form = AssignTestForm(sample=sample)
    # Only offer methods that actually have a spec limit on file for this
    # sample's fuel type — e.g. Freezing Point (D2386) shouldn't show up as
    # assignable on a gasoline sample.
    available_methods = (
        TestMethod.objects.filter(active=True, spec_limits__fuel_type=sample.fuel_type)
        .exclude(id__in=tests.values_list("test_method_id", flat=True))
        .distinct()
    )
    return render(
        request,
        "samples/sample_detail.html",
        {
            "sample": sample,
            "tests": tests,
            "custody_log": custody_log,
            "assign_form": assign_form,
            "available_methods": available_methods,
        },
    )


@login_required
def sample_dispose(request, pk):
    sample = get_object_or_404(Sample, pk=pk)
    if request.method == "POST":
        sample.status = Sample.STATUS_DISPOSED
        sample.save(update_fields=["status", "updated_at"])
        sample.log(request.user, "Sample disposed")
        messages.success(request, f"Sample {sample.sample_id} marked disposed.")
    return redirect("samples:detail", pk=pk)


@login_required
@permission_required("samples.delete_sample", raise_exception=True)
def sample_delete(request, pk):
    """Permanently remove a sample and its tests/results/custody log.

    Restricted to users with the samples.delete_sample permission (Lab
    Manager / QA by default) — Analysts can register and update samples but
    cannot erase records. For routine end-of-life, prefer "Mark disposed"
    (samples:dispose), which keeps the record and its audit trail; this is
    for removing erroneous or duplicate entries.
    """
    sample = get_object_or_404(Sample, pk=pk)
    if request.method == "POST":
        sample_id = sample.sample_id
        sample.delete()
        messages.success(request, f"Sample {sample_id} permanently deleted.")
        return redirect("samples:list")
    return redirect("samples:detail", pk=pk)
