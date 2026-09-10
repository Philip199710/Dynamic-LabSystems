# Data migration: fill in real-world parameters for the seven core QC
# categories Phil asked to have covered on every fuel type — distillation,
# flash point, Karl Fischer (water), conductivity, sediment, density, and
# freezing/low-temperature point — wherever that category is technically
# meaningful for the fuel. Two genuinely new test methods are added because
# the correct real-world apparatus/unit doesn't already exist in the catalog
# (see comments below and in seed_demo.py for full sourcing/reasoning).
#
# This migration also corrects an earlier mistake: Biodiesel (B100) was
# given ASTM D86 IBP/FBP entries in migration 0002, but ASTM D6751 doesn't
# use atmospheric D86 distillation for FAME at all (it boils too high,
# ~330-350C, for D86's atmospheric range without decomposing). Those two
# SpecLimit rows are removed here.
from django.db import migrations

# code, name, standard, unit
NEW_TEST_METHODS = [
    ("PART-D2276", "Particulate Matter Content", "ASTM D2276", "mg/L"),
    ("DIST-D2892", "Distillation, True Boiling Point (TBP)", "ASTM D2892", "°C"),
]

# fuel_code -> {test_code: (min, max)} — brand-new SpecLimit rows.
NEW_SPEC_LIMITS = {
    "GAS95": {
        "FLASH-D56": (-45.0, -20.0),
        "WATER-D6304": (None, 100.0),
        "COND-D2624": (None, None),
        "SED-D473": (None, 0.01),
    },
    "GAS91": {
        "FLASH-D56": (-45.0, -20.0),
        "WATER-D6304": (None, 100.0),
        "COND-D2624": (None, None),
        "SED-D473": (None, 0.01),
    },
    "DIESEL": {
        "COND-D2624": (25.0, None),
    },
    "JETA1": {
        "WATER-D6304": (None, None),
        "PART-D2276": (None, 1.0),
    },
    "B100": {
        "COND-D2624": (None, None),
    },
    "KERO": {
        "WATER-D6304": (None, None),
        "COND-D2624": (None, None),
        "SED-D473": (None, None),
    },
    "MARINE-HFO": {
        "POUR-D97": (None, 0.0),
        "COND-D2624": (None, None),
        "SED-D473": (None, None),
    },
    "MGO": {
        "COND-D2624": (None, None),
        "SED-D473": (None, 0.01),
    },
    "LPG": {
        "WATER-D6304": (None, None),
    },
    "AVGAS100LL": {
        "DENS-D4052": (690.0, 710.0),
        "FLASH-D56": (-45.0, -35.0),
        "WATER-D6304": (None, None),
        "COND-D2624": (None, None),
    },
    "CRUDE": {
        "DIST-D2892": (None, None),
    },
}

# fuel_code -> {test_code: (min, max)} — existing rows whose bounds change.
UPDATED_SPEC_LIMITS = {
    "KERO": {
        # Typical range, shares Jet A-1/kerosene's boiling profile per D3699.
        "DIST-IBP-D86": (150.0, 175.0),
    },
    "LPG": {
        # Typical commercial propane/butane autogas blend range; EN 589
        # doesn't fix a density number (composition-driven).
        "DENS-D4052": (500.0, 580.0),
    },
}
# Prior bounds, for the reverse migration.
PRIOR_SPEC_LIMITS = {
    "KERO": {"DIST-IBP-D86": (None, None)},
    "LPG": {"DENS-D4052": (None, None)},
}

# fuel_code -> [test_code, ...] — rows to remove outright (methodological
# correction: D86 doesn't apply to biodiesel).
REMOVED_SPEC_LIMITS = {
    "B100": ["DIST-IBP-D86", "DISTFBP-D86"],
}


def apply_changes(apps, schema_editor):
    FuelType = apps.get_model("catalog", "FuelType")
    TestMethod = apps.get_model("catalog", "TestMethod")
    SpecLimit = apps.get_model("catalog", "SpecLimit")

    for code, name, standard, unit in NEW_TEST_METHODS:
        TestMethod.objects.get_or_create(
            code=code, defaults={"name": name, "standard_reference": standard, "unit": unit}
        )

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

    for fuel_code, specs in UPDATED_SPEC_LIMITS.items():
        fuel_type = FuelType.objects.filter(code=fuel_code).first()
        if fuel_type is None:
            continue
        for test_code, (min_v, max_v) in specs.items():
            SpecLimit.objects.filter(fuel_type=fuel_type, test_method__code=test_code).update(
                min_value=min_v, max_value=max_v
            )

    for fuel_code, test_codes in REMOVED_SPEC_LIMITS.items():
        fuel_type = FuelType.objects.filter(code=fuel_code).first()
        if fuel_type is None:
            continue
        SpecLimit.objects.filter(fuel_type=fuel_type, test_method__code__in=test_codes).delete()


def revert_changes(apps, schema_editor):
    FuelType = apps.get_model("catalog", "FuelType")
    TestMethod = apps.get_model("catalog", "TestMethod")
    SpecLimit = apps.get_model("catalog", "SpecLimit")

    # Recreate the B100 rows removed above, back to their original blanks.
    b100 = FuelType.objects.filter(code="B100").first()
    if b100 is not None:
        for test_code in REMOVED_SPEC_LIMITS["B100"]:
            test_method = TestMethod.objects.filter(code=test_code).first()
            if test_method is not None:
                SpecLimit.objects.get_or_create(
                    test_method=test_method, fuel_type=b100, defaults={"min_value": None, "max_value": None}
                )

    # Roll back the updated bounds to their prior values.
    for fuel_code, specs in PRIOR_SPEC_LIMITS.items():
        fuel_type = FuelType.objects.filter(code=fuel_code).first()
        if fuel_type is None:
            continue
        for test_code, (min_v, max_v) in specs.items():
            SpecLimit.objects.filter(fuel_type=fuel_type, test_method__code=test_code).update(
                min_value=min_v, max_value=max_v
            )

    # Remove the newly-added SpecLimit rows.
    for fuel_code, specs in NEW_SPEC_LIMITS.items():
        fuel_type = FuelType.objects.filter(code=fuel_code).first()
        if fuel_type is None:
            continue
        SpecLimit.objects.filter(fuel_type=fuel_type, test_method__code__in=specs.keys()).delete()

    # Remove the new test methods themselves, if nothing else references them.
    new_test_codes = [code for code, _, _, _ in NEW_TEST_METHODS]
    for code in new_test_codes:
        tm = TestMethod.objects.filter(code=code).first()
        if tm is not None and not tm.spec_limits.exists():
            tm.delete()


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0005_crude_oil"),
    ]

    operations = [
        migrations.RunPython(apply_changes, revert_changes),
    ]
