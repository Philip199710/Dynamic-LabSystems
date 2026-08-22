from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from samples.models import Sample
from .forms import AssignTestForm, ResultEntryForm
from .models import SampleTest


@login_required
def assign_test(request, sample_pk):
    sample = get_object_or_404(Sample, pk=sample_pk)
    if request.method == "POST":
        form = AssignTestForm(request.POST, sample=sample)
        if form.is_valid():
            sample_test = form.save()
            sample_test.assign(request.user)
            messages.success(request, f"{sample_test.test_method.name} assigned to sample {sample.sample_id}.")
        else:
            messages.error(request, "Could not assign test — check the form.")
    return redirect("samples:detail", pk=sample_pk)


@login_required
def enter_result(request, pk):
    sample_test = get_object_or_404(SampleTest.objects.select_related("sample", "test_method"), pk=pk)
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
            return redirect("samples:detail", pk=sample_test.sample_id)
    else:
        form = ResultEntryForm(instance=existing)
    return render(request, "labtests/result_form.html", {"form": form, "sample_test": sample_test})


@login_required
def my_worklist(request):
    tests = (
        SampleTest.objects.filter(assigned_to=request.user)
        .exclude(status=SampleTest.STATUS_COMPLETE)
        .select_related("sample", "test_method")
        .order_by("due_date")
    )
    return render(request, "labtests/worklist.html", {"tests": tests})
