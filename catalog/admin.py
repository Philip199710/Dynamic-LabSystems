from django.contrib import admin

from .models import FuelType, Instrument, SpecLimit, TestMethod


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


@admin.register(Instrument)
class InstrumentAdmin(admin.ModelAdmin):
    list_display = ("name", "instrument_type", "serial_number", "status", "calibration_due_date")
    list_filter = ("status",)
    search_fields = ("name", "serial_number")
