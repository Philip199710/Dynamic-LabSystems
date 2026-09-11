from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from .models import CalibrationRecord, Instrument


class CalibrationRecordCacheSyncTests(TestCase):
    def setUp(self):
        self.instrument = Instrument.objects.create(
            name="Flash Point Tester #1", instrument_type="Flash point tester", serial_number="FP-001"
        )
        self.today = timezone.localdate()

    def test_creating_a_record_syncs_instrument_cache(self):
        CalibrationRecord.objects.create(
            instrument=self.instrument,
            performed_at=self.today,
            next_due_date=self.today + timedelta(days=365),
        )
        self.instrument.refresh_from_db()
        self.assertEqual(self.instrument.last_calibrated_at, self.today)
        self.assertEqual(self.instrument.calibration_due_date, self.today + timedelta(days=365))

    def test_cache_reflects_most_recently_performed_not_most_recently_entered(self):
        # Enter a recent calibration first...
        CalibrationRecord.objects.create(
            instrument=self.instrument,
            performed_at=self.today,
            next_due_date=self.today + timedelta(days=365),
        )
        # ...then backdate-correct an earlier one. The cache should still
        # resolve to whichever record was actually performed most recently,
        # not whichever row was saved most recently.
        earlier = self.today - timedelta(days=200)
        CalibrationRecord.objects.create(
            instrument=self.instrument,
            performed_at=earlier,
            next_due_date=earlier + timedelta(days=365),
        )
        self.instrument.refresh_from_db()
        self.assertEqual(self.instrument.last_calibrated_at, self.today)
        self.assertEqual(self.instrument.calibration_due_date, self.today + timedelta(days=365))

    def test_no_records_leaves_cache_blank(self):
        self.assertIsNone(self.instrument.last_calibrated_at)
        self.assertIsNone(self.instrument.calibration_due_date)

    def test_record_str(self):
        record = CalibrationRecord.objects.create(instrument=self.instrument, performed_at=self.today)
        self.assertIn(self.instrument.name, str(record))
        self.assertIn(str(self.today), str(record))
