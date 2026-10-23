"""Brake fluid and lubricants, with the lab-instrument tests that apply to each.

Only tests that make sense for the product are linked (no distillation,
freezing point or conductivity on oils/brake fluid). (min, max); None = no
bound, i.e. the result is reported without a pass/fail verdict.

Water limits are typical new-product acceptance limits (brake-fluid purchase
specs; new-oil acceptance), not values from the FMVSS 116 / SAE J300 /
ISO 11158 performance specs, which don't set them. Density and flash point
are product-specific (check the supplier's data sheet) so are report-only
until the lab sets them.
"""

from django.db import migrations

PRODUCTS = {
    # code: (name, description, {method_code: (min, max)})
    "DOT4": (
        "Brake Fluid DOT 4",
        "Glycol-ether brake fluid to FMVSS 116 DOT 4 / SAE J1704 / ISO 4925 Class 4.",
        {"DENS-D1298": (None, None), "WATER-D6304": (None, 2000.0), "FLASH-D93": (None, None)},
    ),
    "SAE50": (
        "Engine Oil SAE 50",
        "Monograde engine oil, SAE J300 viscosity grade 50.",
        {"DENS-D1298": (None, None), "WATER-D6304": (None, 500.0), "FLASH-D93": (None, None), "SED-D473": (None, None)},
    ),
    "HYD68": (
        "Hydraulic Oil ISO VG 68",
        "Anti-wear hydraulic oil, ISO viscosity grade 68 (ISO 11158 HM / DIN 51524-2 HLP).",
        {"DENS-D1298": (None, None), "WATER-D6304": (None, 500.0), "FLASH-D93": (None, None), "SED-D473": (None, None)},
    ),
    "20W50": (
        "Gasoline Engine Oil SAE 20W-50",
        "Multigrade gasoline (petrol) engine oil, SAE J300 20W-50.",
        {"DENS-D1298": (None, None), "WATER-D6304": (None, 500.0), "FLASH-D93": (None, None), "SED-D473": (None, None)},
    ),
}


def forwards(apps, schema_editor):
    FuelType = apps.get_model("catalog", "FuelType")
    TestMethod = apps.get_model("catalog", "TestMethod")
    SpecLimit = apps.get_model("catalog", "SpecLimit")
    methods = {m.code: m for m in TestMethod.objects.filter(code__in=["DENS-D1298", "WATER-D6304", "FLASH-D93", "SED-D473"])}
    for code, (name, description, limits) in PRODUCTS.items():
        product, _ = FuelType.objects.get_or_create(code=code, defaults={"name": name, "description": description})
        for method_code, (lo, hi) in limits.items():
            method = methods.get(method_code)
            if method is not None:
                SpecLimit.objects.get_or_create(
                    test_method=method, fuel_type=product, defaults={"min_value": lo, "max_value": hi}
                )


class Migration(migrations.Migration):
    dependencies = [("catalog", "0012_lab_spec_ranges")]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
