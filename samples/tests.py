from django.contrib.auth import get_user_model
from django.test import TestCase

from catalog.models import FuelType
from .models import Sample

User = get_user_model()


class SampleIdGenerationTests(TestCase):
    def setUp(self):
        self.fuel = FuelType.objects.create(name="Diesel", code="DIESEL")

    def test_sample_id_increments(self):
        s1 = Sample.objects.create(fuel_type=self.fuel, source="A")
        s2 = Sample.objects.create(fuel_type=self.fuel, source="B")
        year = s1.date_received.year
        self.assertEqual(s1.sample_id, f"FS-{year}-0001")
        self.assertEqual(s2.sample_id, f"FS-{year}-0002")

    def test_sample_id_immutable_on_resave(self):
        s1 = Sample.objects.create(fuel_type=self.fuel, source="A")
        original_id = s1.sample_id
        s1.notes = "updated"
        s1.save()
        self.assertEqual(s1.sample_id, original_id)


class ChainOfCustodyTests(TestCase):
    def setUp(self):
        self.fuel = FuelType.objects.create(name="Diesel", code="DIESEL")
        self.user = User.objects.create_user("analyst1", password="x")

    def test_log_creates_entry(self):
        sample = Sample.objects.create(fuel_type=self.fuel, source="A")
        sample.log(self.user, "Sample received")
        self.assertEqual(sample.custody_log.count(), 1)
        entry = sample.custody_log.first()
        self.assertEqual(entry.actor, self.user)
        self.assertEqual(entry.action, "Sample received")


class RecomputeStatusTests(TestCase):
    def setUp(self):
        self.fuel = FuelType.objects.create(name="Diesel", code="DIESEL")
        self.sample = Sample.objects.create(fuel_type=self.fuel, source="A")

    def test_no_tests_stays_received(self):
        self.sample.recompute_status()
        self.assertEqual(self.sample.status, Sample.STATUS_RECEIVED)

    def test_disposed_sample_never_recomputed(self):
        self.sample.status = Sample.STATUS_DISPOSED
        self.sample.save()
        self.sample.recompute_status()
        self.assertEqual(self.sample.status, Sample.STATUS_DISPOSED)
