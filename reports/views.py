import base64
import io
import uuid

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils import timezone
from xhtml2pdf import pisa

from samples.models import Sample

from .charts import build_trend_charts
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
    tests = sample.tests.select_related("test_method", "assigned_to", "testresult", "testresult__instrument").all()
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
                "instrument": result.instrument if result else None,
                "instrument_in_calibration": result.instrument_in_calibration if result else None,
            }
        )
    rows = build_trend_charts(rows)
    return {
        "sample": sample,
        "rows": rows,
        "has_trend_charts": any(row["chart"] for row in rows),
        "certificate": getattr(sample, "certificate", None),
        "generated_at": timezone.localtime(),
        "site_name": settings.SITE_NAME,
        "logo_data_uri": _logo_data_uri(),
    }


def _pdf_safe_html(html):
    """Adjust the certificate HTML for the PDF engine (xhtml2pdf).

    Its built-in fonts have no ≥ / ≤ glyphs, so spec limits read "min" /
    "max" instead of printing as empty boxes.
    """
    for symbol, word in (("\u2265", "min"), ("\u2264", "max")):
        html = html.replace(symbol + " ", word + " ").replace(symbol, word + " ")
    return html


def _give_pdf_images_unique_names():
    """Work around an xhtml2pdf/reportlab image mix-up.

    reportlab names each embedded image after str(image). xhtml2pdf's image
    wrapper doesn't define one, so the name is its memory address, which
    Python reuses once an image has been drawn. Later images then matched
    an earlier one's name and the PDF repeated it: every trend chart on the
    COA came out as the Dynamic logo. A unique id per image fixes that.
    """
    from xhtml2pdf.xhtml2pdf_reportlab import PmlImageReader

    if getattr(PmlImageReader, "_dl_unique_names", False):
        return

    def _name(self):
        uid = self.__dict__.get("_dl_uid")
        if uid is None:
            uid = self.__dict__["_dl_uid"] = uuid.uuid4().hex
        return f"PmlImageReader-{uid}"

    PmlImageReader.__str__ = _name
    PmlImageReader.__repr__ = _name
    PmlImageReader._dl_unique_names = True


def build_coa_pdf_bytes(sample):
    """Render a sample's Certificate of Analysis to PDF bytes (None on failure)."""
    _give_pdf_images_unique_names()
    html = _pdf_safe_html(render_to_string("reports/coa_pdf.html", coa_context(sample)))
    out = io.BytesIO()
    status = pisa.CreatePDF(html, dest=out)
    if status.err:
        return None
    return out.getvalue()


def render_coa_pdf(sample):
    """Render a sample's Certificate of Analysis as a downloadable PDF response."""
    pdf = build_coa_pdf_bytes(sample)
    if pdf is None:
        return HttpResponse("Error generating PDF", status=500)
    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="COA_{sample.sample_id}.pdf"'
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
            from samples import dms

            dms.certificate_issued(certificate)
            messages.success(
                request, f"Certificate {certificate.certificate_number} issued for {sample.sample_id}."
            )
    return redirect("samples:detail", pk=pk)
