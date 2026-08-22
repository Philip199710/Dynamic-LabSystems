import base64

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.template.loader import render_to_string
from django.utils import timezone
from xhtml2pdf import pisa

from samples.models import Sample


def _logo_data_uri():
    logo_path = settings.BASE_DIR / "static" / "img" / "logo.png"
    try:
        with open(logo_path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("ascii")
        return f"data:image/png;base64,{encoded}"
    except FileNotFoundError:
        return ""


@login_required
def sample_coa_pdf(request, pk):
    sample = get_object_or_404(Sample.objects.select_related("fuel_type", "received_by"), pk=pk)
    tests = sample.tests.select_related("test_method", "assigned_to").all()

    rows = []
    for t in tests:
        result = t.result
        limit = t.spec_limit
        rows.append(
            {
                "test_method": t.test_method,
                "result": result,
                "limit": limit,
                "verdict": result.pass_fail if result else None,
            }
        )

    context = {
        "sample": sample,
        "rows": rows,
        "generated_at": timezone.localtime(),
        "site_name": settings.SITE_NAME,
        "logo_data_uri": _logo_data_uri(),
    }
    html = render_to_string("reports/coa_pdf.html", context)

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="COA_{sample.sample_id}.pdf"'
    pisa_status = pisa.CreatePDF(html, dest=response)
    if pisa_status.err:
        return HttpResponse("Error generating PDF", status=500)
    return response


@login_required
def sample_coa_preview(request, pk):
    sample = get_object_or_404(Sample.objects.select_related("fuel_type", "received_by"), pk=pk)
    tests = sample.tests.select_related("test_method", "assigned_to").all()
    rows = []
    for t in tests:
        result = t.result
        limit = t.spec_limit
        rows.append(
            {
                "test_method": t.test_method,
                "result": result,
                "limit": limit,
                "verdict": result.pass_fail if result else None,
            }
        )
    context = {
        "sample": sample,
        "rows": rows,
        "generated_at": timezone.localtime(),
        "site_name": settings.SITE_NAME,
        "logo_data_uri": _logo_data_uri(),
    }
    return render(request, "reports/coa_pdf.html", context)
