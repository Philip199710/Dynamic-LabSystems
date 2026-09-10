# Data migration: add Crude Oil as a fuel type, with its own dedicated
# international assay methods (ISO/ASTM: API gravity D287, BS&W D4007, salt
# content D3230, crude vapor pressure D6377, pour point D97, TAN D664, H2S
# D7621, sulfur by XRF D4294). All spec limits are left blank (record-only,
# no auto pass/fail) — unlike a finished fuel, crude oil is characterized by
# assay, not graded against one fixed international number: different crude
# streams (WTI, Brent, Dubai, Maya, ...) have very different, equally
# "correct" values for the same property. Sources and reasoning are mirrored
# in seed_demo.py's comments.
from django.db import migrations

FUEL_CODE = "CRUDE"
FUEL_NAME = "Crude Oil"
FUEL_DESC = (
    "Unrefined crude petroleum — characterized/assayed, not graded against a fixed pass/fail "
    "spec the way a finished fuel is (different crude streams, e.g. WTI/Brent/Dubai/Maya, have "
    "very different 'normal' values for the same property, none of them 'out of spec'). Its "
    "test methods below are recorded for the assay report, not scored against a min/max."
)

TEST_METHODS = [
    ("API-D287", "API Gravity", "ASTM D287", "°API"),
    ("BSW-D4007", "Water and Sediment (BS&W)", "ASTM D4007", "% vol"),
    ("SALT-D3230", "Salt Content", "ASTM D3230", "PTB"),
    ("VAPOR-D6377", "Vapor Pressure, Crude Oil (VPCRx)", "ASTM D6377", "kPa"),
    ("POUR-D97", "Pour Point", "ASTM D97", "°C"),
    ("TAN-D664", "Total Acid Number (TAN)", "ASTM D664", "mg KOH/g"),
    ("H2S-D7621", "Hydrogen Sulfide Content", "ASTM D7621", "mg/kg"),
    ("SULF-D4294", "Sulfur Content (X-ray Fluorescence)", "ASTM D4294", "% mass"),
]

# Test codes assignable on Crude Oil, including methods that already exist
# in the catalog (density, viscosity, flash point) reused as-is.
SPEC_TEST_CODES = [
    "API-D287",
    "DENS-D4052",
    "SULF-D4294",
    "BSW-D4007",
    "SALT-D3230",
    "VAPOR-D6377",
    "POUR-D97",
    "VISC-D445",
    "TAN-D664",
    "H2S-D7621",
    "FLASH-D93",
]


def add_crude_oil(apps, schema_editor):
    FuelType = apps.get_model("catalog", "FuelType")
    TestMethod = apps.get_model("catalog", "TestMethod")
    SpecLimit = apps.get_model("catalog", "SpecLimit")

    fuel_type, _ = FuelType.objects.get_or_create(
        code=FUEL_CODE, defaults={"name": FUEL_NAME, "description": FUEL_DESC}
    )

    for code, name, standard, unit in TEST_METHODS:
        TestMethod.objects.get_or_create(
            code=code, defaults={"name": name, "standard_reference": standard, "unit": unit}
        )

    for test_code in SPEC_TEST_CODES:
        test_method = TestMethod.objects.filter(code=test_code).first()
        if test_method is None:
            continue
        SpecLimit.objects.get_or_create(
            test_method=test_method, fuel_type=fuel_type, defaults={"min_value": None, "max_value": None}
        )


def remove_crude_oil(apps, schema_editor):
    FuelType = apps.get_model("catalog", "FuelType")
    TestMethod = apps.get_model("catalog", "TestMethod")

    FuelType.objects.filter(code=FUEL_CODE).delete()  # cascades to SpecLimit

    new_test_codes = [code for code, _, _, _ in TEST_METHODS]
    for code in new_test_codes:
        tm = TestMethod.objects.filter(code=code).first()
        if tm is not None and not tm.spec_limits.exists():
            tm.delete()


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0004_marine_lpg_avgas_fuel_types"),
    ]

    operations = [
        migrations.RunPython(add_crude_oil, remove_crude_oil),
    ]
