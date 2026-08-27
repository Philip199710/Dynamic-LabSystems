from django.conf import settings
from django.db import models
from django.db.models import Max
from django.utils import timezone

from catalog.models import FuelType


class Sample(models.Model):
    STATUS_RECEIVED = "RECEIVED"
    STATUS_IN_TESTING = "IN_TESTING"
    STATUS_COMPLETE = "COMPLETE"
    STATUS_DISPOSED = "DISPOSED"
    STATUS_CHOICES = [
        (STATUS_RECEIVED, "Received"),
        (STATUS_IN_TESTING, "In testing"),
        (STATUS_COMPLETE, "Complete"),
        (STATUS_DISPOSED, "Disposed"),
    ]

    sample_id = models.CharField(max_length=20, unique=True, editable=False)
    fuel_type = models.ForeignKey(FuelType, on_delete=models.PROTECT, related_name="samples")
    source = models.CharField(max_length=150, help_text="Client, site, or submitter")
    client = models.ForeignKey(
        "accounts.Client",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="samples",
        help_text="Link to a client-portal account so this sample (and its certificate) shows up in their portal.",
    )
    date_received = models.DateField(default=timezone.localdate)
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="samples_received"
    )
    storage_location = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_RECEIVED)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.sample_id

    def save(self, *args, **kwargs):
        if not self.sample_id:
            self.sample_id = self._generate_sample_id()
        super().save(*args, **kwargs)

    def _generate_sample_id(self):
        year = timezone.localdate().year
        prefix = f"FS-{year}-"
        last = (
            Sample.objects.filter(sample_id__startswith=prefix)
            .aggregate(Max("sample_id"))
            .get("sample_id__max")
        )
        next_n = 1
        if last:
            try:
                next_n = int(last.split("-")[-1]) + 1
            except ValueError:
                next_n = Sample.objects.filter(sample_id__startswith=prefix).count() + 1
        return f"{prefix}{next_n:04d}"

    def recompute_status(self):
        """Roll the sample status up from its tests. Called after test/result changes."""
        if self.status == self.STATUS_DISPOSED:
            return
        tests = list(self.tests.all())
        resolved_statuses = ("COMPLETE", "FAILED_RETEST")
        if not tests:
            new_status = self.STATUS_RECEIVED
        elif all(t.status in resolved_statuses for t in tests):
            new_status = self.STATUS_COMPLETE
        else:
            new_status = self.STATUS_IN_TESTING
        if new_status != self.status:
            self.status = new_status
            self.save(update_fields=["status", "updated_at"])

    def log(self, actor, action, notes=""):
        return ChainOfCustodyEntry.objects.create(sample=self, actor=actor, action=action, notes=notes)


class ChainOfCustodyEntry(models.Model):
    sample = models.ForeignKey(Sample, on_delete=models.CASCADE, related_name="custody_log")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=200)
    notes = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["timestamp"]
        verbose_name_plural = "Chain of custody entries"

    def __str__(self):
        return f"{self.sample.sample_id}: {self.action}"
