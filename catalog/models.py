from django.db import models


class FuelType(models.Model):
    """A fuel grade/product the lab tests, e.g. Gasoline (RON 95), Diesel, Jet A-1."""

    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=20, unique=True, help_text="Short code, e.g. GAS95, DIESEL, JETA1")
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class TestMethod(models.Model):
    """A test/analysis the lab can run, tied to a standard method."""

    code = models.CharField(max_length=20, unique=True, help_text="Short internal code, e.g. FLASH-D93")
    name = models.CharField(max_length=150, help_text="e.g. Flash Point (Pensky-Martens Closed Cup)")
    standard_reference = models.CharField(max_length=100, help_text="e.g. ASTM D93 / IP 34")
    unit = models.CharField(max_length=30, help_text="e.g. °C, kg/m³, mg/kg, kPa, mm²/s")
    description = models.TextField(blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.standard_reference})"


class SpecLimit(models.Model):
    """Acceptable result range for a test method, per fuel type."""

    test_method = models.ForeignKey(TestMethod, on_delete=models.CASCADE, related_name="spec_limits")
    fuel_type = models.ForeignKey(FuelType, on_delete=models.CASCADE, related_name="spec_limits")
    min_value = models.FloatField(null=True, blank=True, help_text="Leave blank if there is no minimum")
    max_value = models.FloatField(null=True, blank=True, help_text="Leave blank if there is no maximum")

    class Meta:
        unique_together = ("test_method", "fuel_type")
        ordering = ["fuel_type__name", "test_method__name"]

    def __str__(self):
        return f"{self.test_method.code} / {self.fuel_type.code}: [{self.min_value}, {self.max_value}]"

    def evaluate(self, value):
        """Return True if value is within spec, False if out of spec, None if unknown."""
        if value is None:
            return None
        if self.min_value is not None and value < self.min_value:
            return False
        if self.max_value is not None and value > self.max_value:
            return False
        return True

    def range_display(self):
        if self.min_value is not None and self.max_value is not None:
            return f"{self.min_value} – {self.max_value}"
        if self.min_value is not None:
            return f"≥ {self.min_value}"
        if self.max_value is not None:
            return f"≤ {self.max_value}"
        return "—"


class Instrument(models.Model):
    """Simple lab instrument/equipment registry."""

    STATUS_ACTIVE = "ACTIVE"
    STATUS_OUT_OF_SERVICE = "OUT_OF_SERVICE"
    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_OUT_OF_SERVICE, "Out of service"),
    ]

    name = models.CharField(max_length=150)
    instrument_type = models.CharField(max_length=100, blank=True, help_text="e.g. Gas Chromatograph, Densitometer")
    serial_number = models.CharField(max_length=100, blank=True)
    location = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    calibration_due_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def calibration_overdue(self):
        from django.utils import timezone

        return bool(self.calibration_due_date and self.calibration_due_date < timezone.localdate())
