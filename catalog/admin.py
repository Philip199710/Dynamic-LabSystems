from django.contrib import admin

from .models import CalibrationRecord, FuelType, Instrument, SpecLimit, TestMethod


@admin.register(FuelType)
class FuelTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "code")
    search_fields = ("name", "code")


class SpecLimitInline(admin.TabularInline):
    model = SpecLimit
    extra = 1


@admin.register(TestMethod)
class TestMethodAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "standard_reference", "unit", "active")
    list_filter = ("active",)
    search_fields = ("code", "name", "standard_reference")
    inlines = [SpecLimitInline]


@admin.register(SpecLimit)
class SpecLimitAdmin(admin.ModelAdmin):
    list_display = ("test_method", "fuel_type", "min_value", "max_value")
    list_filter = ("fuel_type", "test_method")


class CalibrationRecordInline(admin.TabularInline):
    model = CalibrationRecord
    extra = 0
    fields = ("performed_at", "next_due_date", "performed_by", "certificate_reference", "notes")
    ordering = ("-performed_at",)


@admin.register(Instrument)
class InstrumentAdmin(admin.ModelAdmin):
    list_display = ("name", "instrument_type", "serial_number", "status", "last_calibrated_at", "calibration_due_date")
    list_filter = ("status",)
    search_fields = ("name", "serial_number")
    # These two are now a cache derived from CalibrationRecord history
    # (kept in sync by CalibrationRecord.save() -> sync_calibration_cache()),
    # so they're read-only here — log an actual calibration below instead.
    readonly_fields = ("last_calibrated_at", "calibration_due_date")
    inlines = [CalibrationRecordInline]


@admin.register(CalibrationRecord)
class CalibrationRecordAdmin(admin.ModelAdmin):
    list_display = ("instrument", "performed_at", "next_due_date", "performed_by", "certificate_reference")
    list_filter = ("instrument",)
    search_fields = ("instrument__name", "instrument__serial_number", "certificate_reference")
    autocomplete_fields = ("instrument",)
