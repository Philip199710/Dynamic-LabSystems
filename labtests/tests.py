from django.contrib.auth import get_user_model
from django.test import TestCase

from catalog.models import FuelType, SpecLimit, TestMethod
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
