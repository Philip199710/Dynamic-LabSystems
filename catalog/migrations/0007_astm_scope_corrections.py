# Data migration: correct three genuine test-method/standard scope
# mismatches found on a focused accuracy re-audit (sources verified via web
# search this session — see comments below and in seed_demo.py):
#
# 1. ISO 8217 grades a distillate marine fuel's (MGO/DMA) ignition quality
#    by Calculated Cetane Index (ASTM D4737 — a formula from density and
#    distillation temperatures), not an engine-tested Cetane Number
#    (ASTM D613, the method used for automotive diesel). MGO's spec is
#    moved from D613 to D4737, same 40.0 minimum.
# 2. EN 590 (diesel) — and EN 12662 itself, which explicitly also covers
#    FAME — sets a real "Total Contamination" limit (EN 12662, max 24
#    mg/kg) that wasn't on file at all; added for Diesel and Biodiesel.
# 3. ASTM D473 is explicitly scoped to "Crude Oils and Fuel Oils" — it
#    doesn't cover gasoline, a light distillate the extraction method
#    isn't designed for. Gasoline's real particulate-contamination method
#    is ASTM D5452 (laboratory filtration); its D473 rows are removed and
#    replaced with D5452. Gasoline's and Avgas's flash point entries
#    (added in migration 0006) are also removed: ASTM D56 (Tag Closed
#    Cup)'s practical operating range doesn't reliably extend down to
#    these fuels' actual sub-ambient flash points, which is exactly why
#    EN 228/ASTM D910 don't grade flash point for them at all — carrying
#    a number under a method that can't reliably produce it was a mistake.
from django.db import migrations

# code, name, standard, unit
NEW_TEST_METHODS = [
    ("CETANE-D4737", "Cetane Index (Calculated)", "ASTM D4737", "—"),
    ("TOTCONT-EN12662", "Total Contamination", "EN 12662", "mg/kg"),
    ("SED-D5452", "Particulate Contamination (Filtration)", "ASTM D5452", "mg/L"),
]

# fuel_code -> {test_code: (min, max)} — brand-new SpecLimit rows.
NEW_SPEC_LIMITS = {
    "MGO": {"CETANE-D4737": (40.0, None)},
    "DIESEL": {"TOTCONT-EN12662": (None, 24.0)},
    "B100": {"TOTCONT-EN12662": (None, 24.0)},
    "GAS95": {"SED-D5452": (None, 10.0)},
    "GAS91": {"SED-D5452": (None, 10.0)},
}

# fuel_code -> [test_code, ...] — rows removed as scope/method mismatches.
REMOVED_SPEC_LIMITS = {
    "MGO": ["CETANE-D613"],
    "GAS95": ["SED-D473", "FLASH-D56"],
    "GAS91": ["SED-D473", "FLASH-D56"],
    "AVGAS100LL": ["FLASH-D56"],
}
# Bounds those removed rows held, for the reverse migration.
REMOVED_SPEC_BOUNDS = {
    "MGO": {"CETANE-D613": (40.0, None)},
    "GAS95": {"SED-D473": (None, 0.01), "FLASH-D56": (-45.0, -20.0)},
    "GAS91": {"SED-D473": (None, 0.01), "FLASH-D56": (-45.0, -20.0)},
    "AVGAS100LL": {"FLASH-D56": (-45.0, -35.0)},
}


def apply_changes(apps, schema_editor):
    FuelType = apps.get_model("catalog", "FuelType")
    TestMethod = apps.get_model("catalog", "TestMethod")
    SpecLimit = apps.get_model("catalog", "SpecLimit")

    for code, name, standard, unit in NEW_TEST_METHODS:
        TestMethod.objects.get_or_create(
            code=code, defaults={"name": name, "standard_reference": standard, "unit": unit}
        )

    for fuel_code, test_codes in REMOVED_SPEC_LIMITS.items():
        fuel_type = FuelType.objects.filter(code=fuel_code).first()
        if fuel_type is None:
            continue
        SpecLimit.objects.filter(fuel_type=fuel_type, test_method__code__in=test_codes).delete()

    for fuel_code, specs in NEW_SPEC_LIMITS.items():
        fuel_type = FuelType.objects.filter(code=fuel_code).first()
        if fuel_type is None:
            continue
        for test_code, (min_v, max_v) in specs.items():
            test_method = TestMethod.objects.filter(code=test_code).first()
            if test_method is None:
                continue
            SpecLimit.objects.get_or_create(
                test_method=test_method, fuel_type=fuel_type, defaults={"min_value": min_v, "max_value": max_v}
            )


def revert_changes(apps, schema_editor):
    FuelType = apps.get_model("catalog", "FuelType")
    TestMethod = apps.get_model("catalog", "TestMethod")
    SpecLimit = apps.get_model("catalog", "SpecLimit")

    # Undo the new SpecLimit rows.
    for fuel_code, specs in NEW_SPEC_LIMITS.items():
        fuel_type = FuelType.objects.filter(code=fuel_code).first()
        if fuel_type is None:
            continue
        SpecLimit.objects.filter(fuel_type=fuel_type, test_method__code__in=specs.keys()).delete()

    # Recreate the rows that were removed, with their original bounds.
    for fuel_code, bounds in REMOVED_SPEC_BOUNDS.items():
        fuel_type = FuelType.objects.filter(code=fuel_code).first()
        if fuel_type is None:
            continue
        for test_code, (min_v, max_v) in bounds.items():
            test_method = TestMethod.objects.filter(code=test_code).first()
            if test_method is not None:
                SpecLimit.objects.get_or_create(
                    test_method=test_method, fuel_type=fuel_type, defaults={"min_value": min_v, "max_value": max_v}
                )

    new_test_codes = [code for code, _, _, _ in NEW_TEST_METHODS]
    for code in new_test_codes:
        tm = TestMethod.objects.filter(code=code).first()
        if tm is not None and not tm.spec_limits.exists():
            tm.delete()


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0006_full_parameter_coverage"),
    ]

    operations = [
        migrations.RunPython(apply_changes, revert_changes),
    ]
