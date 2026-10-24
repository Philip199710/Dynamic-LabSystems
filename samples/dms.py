"""Event feed to the Dynamic DMS mailbox (settings.DMS_NOTIFICATION_EMAIL).

Three events are sent, one email each:

* sample.registered      a sample is registered at the lab
* sample.tested          every test on a sample has a result (sample Complete)
* certificate.issued     a Certificate of Analysis is issued (PDF attached)

Each email has a readable body for people and an ``event.json`` attachment
with the same data for the DMS to ingest. Sending is best-effort and runs on
a background thread: a mail failure is logged, never shown to the lab, and
never blocks the lab's work.
"""

import json
import logging
import threading

from django.conf import settings
from django.core.mail import EmailMessage
from django.db import close_old_connections, transaction
from django.urls import reverse
from django.utils import timezone

logger = logging.getLogger(__name__)


def _url(path):
    base = (getattr(settings, "SITE_URL", "") or "").rstrip("/")
    return f"{base}{path}" if base else path


def _lab(sample):
    return f"{sample.lab.code} · " if sample.lab_id else ""


def _sample_data(sample):
    return {
        "sample_id": sample.sample_id,
        "lab": sample.lab.name if sample.lab_id else "",
        "lab_code": sample.lab.code if sample.lab_id else "",
        "status": sample.get_status_display(),
        "fuel_type": sample.fuel_type.name,
        "fuel_code": sample.fuel_type.code,
        "source": sample.source,
        "drawn_from": sample.get_source_type_display() if sample.source_type else "",
        "tank_or_tanker_id": sample.tank_or_tanker_id,
        "tanker_plate_number": sample.tanker_plate_number,
        "origin": sample.origin,
        "destination_port": sample.destination_port,
        "client": sample.client.name if sample.client_id else "",
        "date_received": sample.date_received.isoformat() if sample.date_received else "",
        "storage_location": sample.storage_location,
        "received_by": sample.received_by.get_username() if sample.received_by_id else "",
        "notes": sample.notes,
        "url": _url(reverse("samples:detail", args=[sample.pk])),
    }


def _results_data(sample):
    rows = []
    for t in sample.tests.select_related("test_method", "testresult", "testresult__entered_by", "testresult__instrument"):
        result = t.result
        limit = t.spec_limit
        verdict = result.pass_fail if result else None
        rows.append(
            {
                "test": t.test_method.name,
                "standard": t.test_method.standard_reference,
                "value": result.value if result else None,
                "unit": t.test_method.unit,
                "spec_min": limit.min_value if limit else None,
                "spec_max": limit.max_value if limit else None,
                "verdict": {True: "PASS", False: "OUT OF SPEC", None: "NO SPEC"}[verdict],
                "instrument": result.instrument.name if result and result.instrument_id else "",
                "entered_by": result.entered_by.get_username() if result and result.entered_by_id else "",
                "entered_at": timezone.localtime(result.entered_at).isoformat() if result else "",
            }
        )
    return rows


def _lines(pairs):
    width = max(len(k) for k, _ in pairs)
    return "\n".join(f"{k + ':':<{width + 2}}{v if v not in (None, '') else '—'}" for k, v in pairs)


def _deliver(subject, body, event, attachments=()):
    recipient = getattr(settings, "DMS_NOTIFICATION_EMAIL", "")
    if not recipient:
        return
    try:
        msg = EmailMessage(
            subject=subject,
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[recipient],
            headers={"X-Dynamic-Event": event["event"]},
        )
        msg.attach("event.json", json.dumps(event, indent=2, default=str), "application/json")
        for name, content, mimetype in attachments:
            msg.attach(name, content, mimetype)
        msg.send(fail_silently=False)
    except Exception:
        logger.exception("DMS email failed: %s", subject)


def _dispatch(build):
    """Run ``build()`` (which returns the email parts) and send the result,
    on a background thread unless DMS_EMAIL_ASYNC is off."""

    def run():
        try:
            parts = build()
            if parts:
                _deliver(*parts)
        except Exception:
            logger.exception("Building a DMS email failed")
        finally:
            if getattr(settings, "DMS_EMAIL_ASYNC", True):
                close_old_connections()

    def start():
        if getattr(settings, "DMS_EMAIL_ASYNC", True):
            threading.Thread(target=run, daemon=True).start()
        else:
            run()

    # Wait for the surrounding transaction to commit so the email never
    # describes data that was rolled back (and the thread can read it).
    transaction.on_commit(start)


def _event(name, sample, **extra):
    return {
        "event": name,
        "occurred_at": timezone.localtime().isoformat(),
        "lab": settings.SITE_NAME,
        "site_url": getattr(settings, "SITE_URL", ""),
        "sample": _sample_data(sample),
        **extra,
    }


def sample_registered(sample):
    pk = sample.pk

    def build():
        from .models import Sample

        s = Sample.objects.select_related("fuel_type", "received_by", "client", "lab").get(pk=pk)
        data = _sample_data(s)
        body = (
            f"A sample was registered at {settings.SITE_NAME}.\n\n"
            + _lines(
                [
                    ("Sample ID", data["sample_id"]),
                    ("Fuel type", data["fuel_type"]),
                    ("Source", data["source"]),
                    ("Drawn from", data["drawn_from"]),
                    ("Tank / tanker ID", data["tank_or_tanker_id"]),
                    ("Tanker plate", data["tanker_plate_number"]),
                    ("Origin", data["origin"]),
                    ("Destination", data["destination_port"]),
                    ("Date received", data["date_received"]),
                    ("Storage location", data["storage_location"]),
                    ("Received by", data["received_by"]),
                    ("Notes", data["notes"]),
                ]
            )
            + f"\n\nView sample: {data['url']}\n\nAutomated message from {settings.SITE_NAME}. event.json attached."
        )
        return (f"[DMS] {_lab(s)}Sample registered: {s.sample_id}", body, _event("sample.registered", s))

    _dispatch(build)


def sample_tested(sample):
    pk = sample.pk

    def build():
        from .models import Sample

        s = Sample.objects.select_related("fuel_type", "received_by", "client", "lab").get(pk=pk)
        rows = _results_data(s)
        fails = [r for r in rows if r["verdict"] == "OUT OF SPEC"]
        overall = "OUT OF SPEC" if fails else "ALL PASS"
        lines = []
        for r in rows:
            if r["spec_min"] is not None and r["spec_max"] is not None:
                spec = f"{r['spec_min']} to {r['spec_max']}"
            elif r["spec_min"] is not None:
                spec = f"min {r['spec_min']}"
            elif r["spec_max"] is not None:
                spec = f"max {r['spec_max']}"
            else:
                spec = "no spec"
            lines.append(f"- {r['test']} ({r['standard']}): {r['value']} {r['unit']}  [{spec}]  {r['verdict']}")
        body = (
            f"Testing is complete for sample {s.sample_id} ({s.fuel_type.name}, source: {s.source}).\n"
            f"Overall: {overall} ({len(rows)} tests, {len(fails)} out of spec)\n\n"
            + "\n".join(lines)
            + f"\n\nView sample: {_url(reverse('samples:detail', args=[s.pk]))}\n\n"
            f"Automated message from {settings.SITE_NAME}. event.json attached."
        )
        event = _event("sample.tested", s, overall=overall, results=rows)
        return (f"[DMS] {_lab(s)}Sample tested: {s.sample_id} ({overall})", body, event)

    _dispatch(build)


def certificate_issued(certificate):
    pk = certificate.pk

    def build():
        from reports.models import Certificate
        from reports.views import build_coa_pdf_bytes

        c = Certificate.objects.select_related("sample", "sample__fuel_type", "sample__client", "sample__lab", "issued_by").get(pk=pk)
        s = c.sample
        rows = _results_data(s)
        overall = "OUT OF SPEC" if any(r["verdict"] == "OUT OF SPEC" for r in rows) else "ALL PASS"
        pdf = build_coa_pdf_bytes(s)
        body = (
            f"Certificate of Analysis {c.certificate_number} was issued for sample {s.sample_id}.\n\n"
            + _lines(
                [
                    ("Certificate", c.certificate_number),
                    ("Sample ID", s.sample_id),
                    ("Fuel type", s.fuel_type.name),
                    ("Source", s.source),
                    ("Client", s.client.name if s.client_id else ""),
                    ("Overall", overall),
                    ("Issued by", c.issued_by.get_username() if c.issued_by_id else ""),
                    ("Issued at", timezone.localtime(c.issued_at).strftime("%d %b %Y %H:%M")),
                ]
            )
            + ("\n\nThe certificate PDF is attached." if pdf else "\n\nThe PDF could not be generated; open it in the system.")
            + f"\n\nView sample: {_url(reverse('samples:detail', args=[s.pk]))}\n\nAutomated message from {settings.SITE_NAME}."
        )
        event = _event(
            "certificate.issued",
            s,
            certificate={
                "number": c.certificate_number,
                "issued_at": timezone.localtime(c.issued_at).isoformat(),
                "issued_by": c.issued_by.get_username() if c.issued_by_id else "",
            },
            overall=overall,
            results=rows,
        )
        attachments = [(f"COA_{c.certificate_number}.pdf", pdf, "application/pdf")] if pdf else []
        return (f"[DMS] {_lab(s)}COA issued: {c.certificate_number} for {s.sample_id}", body, event, attachments)

    _dispatch(build)
