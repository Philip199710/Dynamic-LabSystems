from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from catalog.models import CalibrationRecord, FuelType, Instrument, SpecLimit, TestMethod
from samples.models import Sample
from .models import SampleTest, TestResult

User = get_user_model()


class SpecLimitEvaluateTests(TestCase):
    def test_within_both_bounds(self):
        limit = SpecLimit(min_value=10, max_value=20)
        self.assertTrue(limit.evaluate(15))

    def test_below_min(self):
        limit = SpecLimit(min_value=10, max_value=20)
        self.assertFalse(limit.evaluate(5))

    def test_above_max(self):
        limit = SpecLimit(min_value=10, max_value=20)
        self.assertFalse(limit.evaluate(25))

    def test_min_only(self):
        limit = SpecLimit(min_value=10, max_value=None)
        self.assertTrue(limit.evaluate(1000))
        self.assertFalse(limit.evaluate(5))

    def test_no_bounds_unknown_value_none(self):
        limit = SpecLimit(min_value=None, max_value=None)
        self.assertIsNone(limit.evaluate(None))


class TestResultRecordTests(TestCase):
    def setUp(self):
        self.fuel = FuelType.objects.create(name="Diesel", code="DIESEL")
        self.method = TestMethod.objects.create(
            code="CETANE-D613", name="Cetane Number", standard_reference="ASTM D613", unit="—"
        )
        SpecLimit.objects.create(test_method=self.method, fuel_type=self.fuel, min_value=51, max_value=None)
        self.sample = Sample.objects.create(fuel_type=self.fuel, source="A")
        self.analyst = User.objects.create_user("analyst1", password="x")
        self.sample_test = SampleTest.objects.create(sample=self.sample, test_method=self.method)

    def test_passing_result_completes_test_and_sample(self):
        result = TestResult(sample_test=self.sample_test, value=58.0, entered_by=self.analyst)
        result.record(self.analyst)

        self.sample_test.refresh_from_db()
        self.sample.refresh_from_db()
        self.assertEqual(self.sample_test.status, SampleTest.STATUS_COMPLETE)
        self.assertEqual(self.sample.status, Sample.STATUS_COMPLETE)
        self.assertTrue(result.pass_fail)

    def test_failing_result_marks_failed_retest_but_sample_still_resolves(self):
        result = TestResult(sample_test=self.sample_test, value=40.0, entered_by=self.analyst)
        result.record(self.analyst)

        self.sample_test.refresh_from_db()
        self.sample.refresh_from_db()
        self.assertEqual(self.sample_test.status, SampleTest.STATUS_FAILED_RETEST)
        self.assertEqual(self.sample.status, Sample.STATUS_COMPLETE)
        self.assertFalse(result.pass_fail)

    def test_record_logs_chain_of_custody(self):
        result = TestResult(sample_test=self.sample_test, value=58.0, entered_by=self.analyst)
        result.record(self.analyst)
        actions = list(self.sample.custody_log.values_list("action", flat=True))
        self.assertTrue(any("Result entered" in a for a in actions))

    def test_assign_logs_chain_of_custody_and_moves_sample_to_in_testing(self):
        self.sample_test.assign(self.analyst)
        self.sample.refresh_from_db()
        self.assertEqual(self.sample.status, Sample.STATUS_IN_TESTING)
        actions = list(self.sample.custody_log.values_list("action", flat=True))
        self.assertTrue(any("Test assigned" in a for a in actions))


class InstrumentInCalibrationTests(TestCase):
    """TestResult.instrument_in_calibration must reflect calibration status
    *at the time the result was entered*, not the instrument's status today —
    so a result stays correctly flagged even after the instrument is later
    recalibrated (or its calibration lapses after the fact).
    """

    def setUp(self):
        self.fuel = FuelType.objects.create(name="Diesel", code="DIESEL")
        self.method = TestMethod.objects.create(
            code="CETANE-D613", name="Cetane Number", standard_reference="ASTM D613", unit="—"
        )
        SpecLimit.objects.create(test_method=self.method, fuel_type=self.fuel, min_value=51, max_value=None)
        self.sample = Sample.objects.create(fuel_type=self.fuel, source="A")
        self.analyst = User.objects.create_user("analyst2", password="x")
        self.sample_test = SampleTest.objects.create(sample=self.sample, test_method=self.method)
        self.instrument = Instrument.objects.create(
            name="Cetane Engine #1", instrument_type="Cetane engine", serial_number="CE-001"
        )
        self.today = timezone.localdate()

    def _make_result(self, entered_at):
        result = TestResult(
            sample_test=self.sample_test, value=58.0, entered_by=self.analyst, instrument=self.instrument
        )
        result.record(self.analyst)
        # record() stamps entered_at itself; override it after the fact to
        # simulate a result entered at a specific point in time.
        TestResult.objects.filter(pk=result.pk).update(entered_at=entered_at)
        result.refresh_from_db()
        return result

    def test_no_instrument_returns_none(self):
        result = TestResult(sample_test=self.sample_test, value=58.0, entered_by=self.analyst)
        result.record(self.analyst)
        self.assertIsNone(result.instrument_in_calibration)

    def test_no_calibration_history_returns_none(self):
        result = self._make_result(timezone.now())
        self.assertIsNone(result.instrument_in_calibration)

    def test_in_calibration_at_time_of_entry(self):
        CalibrationRecord.objects.create(
            instrument=self.instrument,
            performed_at=self.today - timedelta(days=30),
            next_due_date=self.today + timedelta(days=335),
        )
        result = self._make_result(timezone.now())
        self.assertTrue(result.instrument_in_calibration)

    def test_overdue_at_time_of_entry(self):
        CalibrationRecord.objects.create(
            instrument=self.instrument,
            performed_at=self.today - timedelta(days=400),
            next_due_date=self.today - timedelta(days=35),
        )
        result = self._make_result(timezone.now())
        self.assertFalse(result.instrument_in_calibration)

    def test_stays_correctly_flagged_after_later_recalibration(self):
        # Result entered while overdue...
        CalibrationRecord.objects.create(
            instrument=self.instrument,
            performed_at=self.today - timedelta(days=400),
            next_due_date=self.today - timedelta(days=35),
        )
        stale_entry_date = timezone.now() - timedelta(days=1)
        result = self._make_result(stale_entry_date)
        self.assertFalse(result.instrument_in_calibration)

        # ...then the instrument gets recalibrated today. The historical
        # result should still show it was out of calibration when entered.
        CalibrationRecord.objects.create(
            instrument=self.instrument,
            performed_at=self.today,
            next_due_date=self.today + timedelta(days=365),
        )
        result.refresh_from_db()
        self.assertFalse(result.instrument_in_calibration)

        # A brand-new result entered today, though, should read as in-calibration.
        # Use a second sample/test pair since (sample, test_method) is unique.
        other_sample = Sample.objects.create(fuel_type=self.fuel, source="B")
        new_result = TestResult(
            sample_test=SampleTest.objects.create(sample=other_sample, test_method=self.method),
            value=58.0,
            entered_by=self.analyst,
            instrument=self.instrument,
        )
        new_result.record(self.analyst)
        self.assertTrue(new_result.instrument_in_calibration)
