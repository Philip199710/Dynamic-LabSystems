# Data migration: add ASTM D86 Initial Boiling Point (IBP) as a recordable
# test method, and make Final Boiling Point (FBP) recordable for the two fuel
# types that didn't have it yet (Diesel, Biodiesel/B100). Neither gets a
# pass/fail spec range yet — both bounds are left blank so results record
# without an automatic PASS/FAIL verdict (see SpecLimit.evaluate()) until
# real acceptance limits are supplied.
from django.db import migrations

# Fuel type codes this applies to (all fuel types currently in the catalog).
FUEL_CODES = ["GAS95", "GAS91", "DIESEL", "JETA1", "B100", "KERO"]

# Fuel types that don't already have a Final Boiling Point (DISTFBP-D86) spec
# on file — add a blank/blank row so it becomes assignable for them too.
FBP_FUEL_CODES = ["DIESEL", "B100"]

IBP_CODE = "DIST-IBP-D86"
FBP_CODE = "DISTFBP-D86"


def add_ibp(apps, schema_editor):
    FuelType = apps.get_model("catalog", "FuelType")
    TestMethod = apps.get_model("catalog", "TestMethod")
    SpecLimit = apps.get_model("catalog", "SpecLimit")

    ibp_method, _ = TestMethod.objects.get_or_create(
        code=IBP_CODE,
        defaults={
            "name": "Distillation, Initial Boiling Point (IBP)",
            "standard_reference": "ASTM D86",
            "unit": "°C",
        },
    )

    for code in FUEL_CODES:
        fuel_type = FuelType.objects.filter(code=code).first()
        if fuel_type is None:
            continue
        SpecLimit.objects.get_or_create(
            test_method=ibp_method, fuel_type=fuel_type, defaults={"min_value": None, "max_value": None}
        )

    fbp_method = TestMethod.objects.filter(code=FBP_CODE).first()
    if fbp_method is not None:
        for code in FBP_FUEL_CODES:
            fuel_type = FuelType.objects.filter(code=code).first()
            if fuel_type is None:
                continue
            SpecLimit.objects.get_or_create(
                test_method=fbp_method, fuel_type=fuel_type, defaults={"min_value": None, "max_value": None}
            )


def remove_ibp(apps, schema_editor):
    TestMethod = apps.get_model("catalog", "TestMethod")
    SpecLimit = apps.get_model("catalog", "SpecLimit")
    FuelType = apps.get_model("catalog", "FuelType")

    ibp_method = TestMethod.objects.filter(code=IBP_CODE).first()
    if ibp_method is not None:
        SpecLimit.objects.filter(test_method=ibp_method).delete()
        ibp_method.delete()

    fbp_method = TestMethod.objects.filter(code=FBP_CODE).first()
    if fbp_method is not None:
        fuel_types = FuelType.objects.filter(code__in=FBP_FUEL_CODES)
        SpecLimit.objects.filter(test_method=fbp_method, fuel_type__in=fuel_types, min_value__isnull=True, max_value__isnull=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(add_ibp, remove_ibp),
    ]
