import statistics
from collections import defaultdict

from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from catalog.models import Instrument, TestMethod
from labtests.models import SampleTest, TestResult
from samples.models import ChainOfCustodyEntry, Sample


@login_required
def home(request):
    status_counts = {row["status"]: row["count"] for row in Sample.objects.values("status").annotate(count=Count("id"))}
    status_display = dict(Sample.STATUS_CHOICES)
    status_summary = [
        {"key": key, "label": label, "count": status_counts.get(key, 0)} for key, label in Sample.STATUS_CHOICES
    ]

    open_tests = (
        SampleTest.objects.exclude(status=SampleTest.STATUS_COMPLETE)
        .select_related("sample", "test_method", "assigned_to")
        .order_by("due_date")
    )
    overdue_tests = [t for t in open_tests if t.overdue]

    workload = defaultdict(int)
    for t in open_tests:
        name = t.assigned_to.get_username() if t.assigned_to else "Unassigned"
        workload[name] += 1
    workload = sorted(workload.items(), key=lambda kv: -kv[1])

    recent_activity = ChainOfCustodyEntry.objects.select_related("sample", "actor").order_by("-timestamp")[:15]

    results = TestResult.objects.select_related("sample_test__test_method")
    total_results = results.count()
    fail_count = sum(1 for r in results if r.pass_fail is False)
    pass_count = sum(1 for r in results if r.pass_fail is True)

    completed = Sample.objects.filter(status=Sample.STATUS_COMPLETE)
    turnaround_days = []
    for s in completed:
        days = (s.updated_at.date() - s.date_received).days
        if days >= 0:
            turnaround_days.append(days)
    avg_turnaround = round(statistics.mean(turnaround_days), 1) if turnaround_days else None

    instruments_due = Instrument.objects.filter(
        calibration_due_date__isnull=False, calibration_due_date__lt=timezone.localdate()
    )

    context = {
        "status_summary": status_summary,
        "total_samples": Sample.objects.count(),
        "open_tests_count": len(list(open_tests)),
        "overdue_tests": overdue_tests,
        "workload": workload,
        "recent_activity": recent_activity,
        "total_results": total_results,
        "pass_count": pass_count,
        "fail_count": fail_count,
        "avg_turnaround": avg_turnaround,
        "instruments_due": instruments_due,
    }
    return render(request, "dashboard/home.html", context)


@login_required
def analytics_index(request):
    methods = TestMethod.objects.filter(active=True).order_by("name")
    method_counts = {
        row["sample_test__test_method"]: row["n"]
        for row in TestResult.objects.values("sample_test__test_method").annotate(n=Count("id"))
    }
    for m in methods:
        m.result_count = method_counts.get(m.id, 0)
    return render(request, "dashboard/analytics_index.html", {"methods": methods})


@login_required
def analytics_trend(request, method_id):
    method = get_object_or_404(TestMethod, pk=method_id)
    results = (
        TestResult.objects.filter(sample_test__test_method=method)
        .select_related("sample_test__sample")
        .order_by("entered_at")
    )

    points = []
    values = []
    for r in results:
        values.append(r.value)
        points.append(
            {
                "label": r.sample_test.sample.sample_id,
                "date": timezone.localtime(r.entered_at).strftime("%Y-%m-%d"),
                "value": r.value,
                "pass_fail": r.pass_fail,
            }
        )

    mean = round(statistics.mean(values), 4) if values else None
    stdev = round(statistics.pstdev(values), 4) if len(values) > 1 else 0
    fuel_types = list(method.spec_limits.select_related("fuel_type").all())

    context = {
        "method": method,
        "points": points,
        "mean": mean,
        "stdev": stdev,
        "ucl2": round(mean + 2 * stdev, 4) if mean is not None else None,
        "lcl2": round(mean - 2 * stdev, 4) if mean is not None else None,
        "ucl3": round(mean + 3 * stdev, 4) if mean is not None else None,
        "lcl3": round(mean - 3 * stdev, 4) if mean is not None else None,
        "fuel_types": fuel_types,
        "pass_count": sum(1 for p in points if p["pass_fail"] is True),
        "fail_count": sum(1 for p in points if p["pass_fail"] is False),
    }
    return render(request, "dashboard/analytics_trend.html", context)
