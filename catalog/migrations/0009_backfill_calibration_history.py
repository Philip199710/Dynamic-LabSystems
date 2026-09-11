# Data migration: every Instrument already has a `calibration_due_date`
# from before calibration became a real log (migration 0008 added
# CalibrationRecord). Rather than let that history disappear, this backfills
# one CalibrationRecord per instrument that already has a due date on file.
#
# The original single-date field never recorded when the instrument was
# LAST calibrated — only when it's next due — so the exact original
# calibration date is genuinely unknown. This assumes a typical 365-day
# annual calibration cycle (performed_at = due_date - 365 days) rather than
# leaving the history blank; every backfilled row is clearly marked in its
# notes so nobody mistakes the assumed date for a real logged event.
from datetime import timedelta

from django.db import migrations

ASSUMED_CALIBRATION_INTERVAL_DAYS = 365


def backfill(apps, schema_editor):
    Instrument = apps.get_model("catalog", "Instrument")
    CalibrationRecord = apps.get_model("catalog", "CalibrationRecord")

    for instrument in Instrument.objects.filter(calibration_due_date__isnull=False):
        if instrument.calibration_records.exists():
            continue
        performed_at = instrument.calibration_due_date - timedelta(days=ASSUMED_CALIBRATION_INTERVAL_DAYS)
        CalibrationRecord.objects.create(
            instrument=instrument,
            performed_at=performed_at,
            next_due_date=instrument.calibration_due_date,
            certificate_reference="",
            notes=(
                "Backfilled automatically when calibration logging was introduced — the prior "
                "single-date field only recorded the due date, not when the instrument was last "
                "actually calibrated, so this performed_at date is an assumed 365-day cycle "
                "working backward from the due date on file, not a real logged event."
            ),
        )
        instrument.last_calibrated_at = performed_at
        instrument.save(update_fields=["last_calibrated_at"])


def unbackfill(apps, schema_editor):
    CalibrationRecord = apps.get_model("catalog", "CalibrationRecord")
    Instrument = apps.get_model("catalog", "Instrument")

    backfilled = CalibrationRecord.objects.filter(certificate_reference="", notes__startswith="Backfilled automatically")
    instrument_ids = list(backfilled.values_list("instrument_id", flat=True))
    backfilled.delete()
    for instrument in Instrument.objects.filter(id__in=instrument_ids):
        instrument.last_calibrated_at = None
        instrument.save(update_fields=["last_calibrated_at"])


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0008_instrument_last_calibrated_at_calibrationrecord"),
    ]

    operations = [
        migrations.RunPython(backfill, unbackfill),
    ]
