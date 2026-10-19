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


class LabEquipmentTests(TestCase):
    """The lab's real equipment ships with the app (migration 0011)."""

    EXPECTED = {
        "KFT-40VC": ["ASTM D6304"],
        "AWD-33": ["ASTM D473"],
        "AWD-18A": ["ASTM D1298"],
        "AWD-02": ["ASTM D93"],
        "AWD-1803": ["ASTM D2386"],
        "Model 1152": ["ASTM D2624"],
        "AWD-05C": ["ASTM D86"],
    }

    def test_all_seven_instruments_with_their_standards(self):
        from catalog.models import Instrument

        for model, standards in self.EXPECTED.items():
            inst = Instrument.objects.get(model_number=model)
            self.assertEqual(inst.status, Instrument.STATUS_ACTIVE)
            self.assertEqual(sorted(set(inst.test_methods.values_list("standard_reference", flat=True))), standards)
        self.assertEqual(Instrument.objects.get(model_number="AWD-05C").test_methods.count(), 4)
