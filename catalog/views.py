from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import CalibrationRecordForm
from .models import Instrument


@login_required
def instrument_list(request):
    instruments = Instrument.objects.all().order_by("name")
    return render(request, "catalog/instrument_list.html", {"instruments": instruments})


@login_required
def instrument_detail(request, pk):
    instrument = get_object_or_404(Instrument, pk=pk)
    records = instrument.calibration_records.select_related("performed_by").all()

    if request.method == "POST":
        if not request.user.has_perm("catalog.add_calibrationrecord"):
            messages.error(request, "You don't have permission to record a calibration.")
            return redirect("catalog:instrument_detail", pk=pk)
        form = CalibrationRecordForm(request.POST)
        if form.is_valid():
            record = form.save(commit=False)
            record.instrument = instrument
            record.performed_by = request.user
            record.save()
            messages.success(
                request,
                f"Calibration recorded for {instrument.name}"
                + (f" — next due {record.next_due_date}." if record.next_due_date else "."),
            )
            return redirect("catalog:instrument_detail", pk=pk)
        messages.error(request, "Could not record calibration — check the form.")
    else:
        form = CalibrationRecordForm(initial={"performed_at": timezone.localdate()})

    results_using = instrument.test_results.select_related(
        "sample_test__sample", "sample_test__test_method"
    ).order_by("-entered_at")[:20]

    return render(
        request,
        "catalog/instrument_detail.html",
        {
            "instrument": instrument,
            "records": records,
            "form": form,
            "results_using": results_using,
            "results_count": instrument.test_results.count(),
        },
    )
