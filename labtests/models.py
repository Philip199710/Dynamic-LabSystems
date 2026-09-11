from django.conf import settings
from django.db import models
from django.utils import timezone

from catalog.models import Instrument, SpecLimit, TestMethod
from samples.models import Sample


class SampleTest(models.Model):
    STATUS_PENDING = "PENDING"
    STATUS_IN_PROGRESS = "IN_PROGRESS"
    STATUS_COMPLETE = "COMPLETE"
    STATUS_FAILED_RETEST = "FAILED_RETEST"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_IN_PROGRESS, "In progress"),
        (STATUS_COMPLETE, "Complete"),
        (STATUS_FAILED_RETEST, "Failed — retest"),
    ]

    sample = models.ForeignKey(Sample, on_delete=models.CASCADE, related_name="tests")
    test_method = models.ForeignKey(TestMethod, on_delete=models.PROTECT, related_name="sample_tests")
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_tests"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    due_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["due_date", "created_at"]
        unique_together = ("sample", "test_method")

    def __str__(self):
        return f"{self.sample.sample_id} / {self.test_method.code}"

    @property
    def spec_limit(self):
        return SpecLimit.objects.filter(test_method=self.test_method, fuel_type=self.sample.fuel_type).first()

    @property
    def overdue(self):
        return bool(
            self.due_date
            and self.due_date < timezone.localdate()
            and self.status not in (self.STATUS_COMPLETE,)
        )

    @property
    def result(self):
        return getattr(self, "testresult", None)

    def assign(self, actor, notes=""):
        self.sample.log(
            actor,
            f"Test assigned: {self.test_method.name}",
            notes=notes or (f"Due {self.due_date}" if self.due_date else ""),
        )
        self.sample.recompute_status()


class TestResult(models.Model):
    sample_test = models.OneToOneField(SampleTest, on_delete=models.CASCADE, related_name="testresult")
    value = models.FloatField()
    replicate_values = models.CharField(
        max_length=200, blank=True, help_text="Optional comma-separated replicate readings, e.g. 0.812, 0.814, 0.813"
    )
    instrument = models.ForeignKey(
        Instrument,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="test_results",
        help_text="Which instrument produced this reading, if applicable",
    )
    entered_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    entered_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["entered_at"]

    def __str__(self):
        return f"{self.sample_test} = {self.value}"

    @property
    def unit(self):
        return self.sample_test.test_method.unit

    @property
    def pass_fail(self):
        """True (pass), False (fail), or None (no spec limit defined)."""
        limit = self.sample_test.spec_limit
        if limit is None:
            return None
        return limit.evaluate(self.value)

    @property
    def instrument_in_calibration(self):
        """Was the recorded instrument in calibration at the moment this result was entered?

        True/False when there's a calibration history to check it against;
        None when no instrument was recorded, or no calibration record
        covers this result's entry date (so there's nothing to flag either
        way). Looks at the calibration record that was current *at the time
        the result was entered* — not the instrument's calibration status
        today — so this stays a correct point-in-time answer even after
        the instrument has since been recalibrated (or gone overdue since).
        """
        if not self.instrument_id or not self.entered_at:
            return None
        entered_date = self.entered_at.date() if hasattr(self.entered_at, "date") else self.entered_at
        record = (
            self.instrument.calibration_records.filter(performed_at__lte=entered_date)
            .order_by("-performed_at", "-created_at")
            .first()
        )
        if record is None or record.next_due_date is None:
            return None
        return entered_date <= record.next_due_date

    def record(self, actor):
        """Persist the result and cascade status/chain-of-custody updates. Call instead of bare .save()."""
        self.save()
        sample_test = self.sample_test
        verdict = self.pass_fail
        if verdict is False:
            sample_test.status = SampleTest.STATUS_FAILED_RETEST
        else:
            sample_test.status = SampleTest.STATUS_COMPLETE
        sample_test.save(update_fields=["status"])

        verdict_label = {True: "PASS", False: "OUT OF SPEC", None: "recorded (no spec on file)"}[verdict]
        sample_test.sample.log(
            actor,
            f"Result entered: {sample_test.test_method.name} = {self.value} {self.unit} ({verdict_label})",
        )
        sample_test.sample.recompute_status()
        return self
