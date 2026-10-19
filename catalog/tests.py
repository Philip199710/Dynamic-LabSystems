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


class AssignableMethodsTests(TestCase):
    def test_every_lab_method_assignable_even_without_spec(self):
        from catalog.models import FuelType
        from labtests.forms import AssignTestForm
        from samples.models import Sample

        fuel = FuelType.objects.create(name="Test Avgas", code="AVGTEST")  # no spec limits at all
        sample = Sample.objects.create(fuel_type=fuel, source="A")
        form = AssignTestForm(sample=sample)
        codes = set(form.fields["test_method"].queryset.values_list("code", flat=True))
        self.assertEqual(codes, {"WATER-D6304", "SED-D473", "DENS-D1298", "FLASH-D93", "FREEZE-D2386", "COND-D2624",
                                 "DIST-IBP-D86", "DIST10-D86", "DIST-D86", "DISTFBP-D86"})

    def test_spec_ranges_for_main_products(self):
        from catalog.models import SpecLimit

        def lim(fuel, code):
            sl = SpecLimit.objects.get(fuel_type__code=fuel, test_method__code=code)
            return (sl.min_value, sl.max_value)

        self.assertEqual(lim("JETA1", "FREEZE-D2386"), (None, -47.0))
        self.assertEqual(lim("JETA1", "COND-D2624"), (50.0, 600.0))
        self.assertEqual(lim("DIESEL", "FLASH-D93"), (55.0, None))
        self.assertEqual(lim("GAS95", "DENS-D1298"), (720.0, 775.0))
        self.assertEqual(lim("KERO", "FREEZE-D2386"), (None, -30.0))
        for fuel in ["JETA1", "DIESEL", "GAS95", "GAS91", "KERO"]:
            self.assertEqual(SpecLimit.objects.filter(fuel_type__code=fuel, test_method__instruments__isnull=False).distinct().count(), 10)
