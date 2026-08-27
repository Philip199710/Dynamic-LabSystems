import base64

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils import timezone
from xhtml2pdf import pisa

from samples.models import Sample

from .models import Certificate


def _logo_data_uri():
    logo_path = settings.BASE_DIR / "static" / "img" / "logo.png"
    try:
        with open(logo_path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("ascii")
        return f"data:image/png;base64,{encoded}"
    except FileNotFoundError:
        return ""


def coa_context(sample):
    """Build the template context for a Certificate of Analysis.

    Shared by the staff-facing reports views below and the client-portal
    views in accounts.views, so both render the exact same certificate.
    """
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
    return {
        "sample": sample,
        "rows": rows,
        "certificate": getattr(sample, "certificate", None),
        "generated_at": timezone.localtime(),
        "site_name": settings.SITE_NAME,
        "logo_data_uri": _logo_data_uri(),
    }


def render_coa_pdf(sample):
    """Render a sample's Certificate of Analysis as a downloadable PDF response."""
    html = render_to_string("reports/coa_pdf.html", coa_context(sample))
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="COA_{sample.sample_id}.pdf"'
    pisa_status = pisa.CreatePDF(html, dest=response)
    if pisa_status.err:
        return HttpResponse("Error generating PDF", status=500)
    return response


@login_required
def sample_coa_pdf(request, pk):
    sample = get_object_or_404(Sample.objects.select_related("fuel_type", "received_by"), pk=pk)
    return render_coa_pdf(sample)


@login_required
def sample_coa_preview(request, pk):
    sample = get_object_or_404(Sample.objects.select_related("fuel_type", "received_by"), pk=pk)
    return render(request, "reports/coa_pdf.html", coa_context(sample))


@login_required
@permission_required("reports.add_certificate", raise_exception=True)
def issue_certificate(request, pk):
    """Formally issue a Certificate of Analysis for a completed sample.

    Distinct from the always-available "download COA" export: this stamps a
    permanent certificate number and is what makes the certificate appear
    in the client portal. Gated on reports.add_certificate (Lab Manager/QA
    by default) so Analysts can enter results but not sign off on them.
    """
    sample = get_object_or_404(Sample, pk=pk)
    if request.method == "POST":
        if sample.status != Sample.STATUS_COMPLETE:
            messages.error(
                request,
                f"{sample.sample_id} isn't marked Complete yet — finish and review all tests before issuing a certificate.",
            )
        elif hasattr(sample, "certificate"):
            messages.info(
                request,
                f"Certificate {sample.certificate.certificate_number} was already issued for {sample.sample_id}.",
            )
        else:
            certificate = Certificate.objects.create(sample=sample, issued_by=request.user)
            sample.log(request.user, "Certificate issued", notes=certificate.certificate_number)
            messages.success(
                request, f"Certificate {certificate.certificate_number} issued for {sample.sample_id}."
            )
    return redirect("samples:detail", pk=pk)
