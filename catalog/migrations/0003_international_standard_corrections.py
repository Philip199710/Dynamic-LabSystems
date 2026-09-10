# Data migration: bring the test catalog in line with the actual published
# international standards it's meant to follow. Found during an audit
# against EN 228 (gasoline), EN 590 (diesel), DEF STAN 91-091 / ASTM D1655
# (Jet A-1), ASTM D6751 + EN 14214 (biodiesel), and ASTM D3699 (kerosene):
#
#   - Gasoline (RON95/RON91): distillation T10 and FBP limits didn't match
#     EN 228 (T10 <= 50C not 70C; FBP <= 210C not 225C).
#   - Jet A-1: its viscosity limit (<=8.0 mm2/s) was recorded under a test
#     method labelled "at 40C", but Jet A-1's spec condition is -20C. Split
#     into a dedicated -20C method so the recorded condition is accurate.
#   - Biodiesel (B100): sulfur cap corrected to the D6751 "S15" grade
#     (<=15 mg/kg, was 10); viscosity widened to the full D6751 allowable
#     range (1.9-6.0 mm2/s, was an unexplained 3.5-5.0); added the missing
#     Cetane Number minimum (>=47) that D6751 requires but had no row at all.
#   - Kerosene: sulfur cap corrected to the ASTM D3699 No. 1-K
#     illuminating/heating grade (<=400 mg/kg, was 2000 — roughly the No. 2-K
#     heating-only grade, which doesn't match this fuel type's own
#     description).
#   - Diesel: audited against EN 590 — already matched exactly, no changes.
#
# All numeric sources and reasoning are mirrored in seed_demo.py's comments.
from django.db import migrations

VISC_LOW_CODE = "VISC-D445-LOW"
VISC_40_CODE = "VISC-D445"
CETANE_CODE = "CETANE-D613"

# (fuel_code, test_code, new_min, new_max)
NUMERIC_CORRECTIONS = [
    ("GAS95", "DIST10-D86", None, 50.0),
    ("GAS95", "DISTFBP-D86", None, 210.0),
    ("GAS91", "DIST10-D86", None, 50.0),
    ("GAS91", "DISTFBP-D86", None, 210.0),
    ("B100", "SULF-D5453", None, 15.0),
    ("B100", VISC_40_CODE, 1.9, 6.0),
    ("KERO", "SULF-D5453", None, 400.0),
]


def apply_corrections(apps, schema_editor):
    FuelType = apps.get_model("catalog", "FuelType")
    TestMethod = apps.get_model("catalog", "TestMethod")
    SpecLimit = apps.get_model("catalog", "SpecLimit")

    # 1. Add the Jet-A-1-specific -20C viscosity method.
    visc_low, _ = TestMethod.objects.get_or_create(
        code=VISC_LOW_CODE,
        defaults={
            "name": "Kinematic Viscosity at -20°C",
            "standard_reference": "ASTM D445",
            "unit": "mm²/s",
        },
    )

    # 2. Move Jet A-1's viscosity spec off the (wrongly-labelled-for-it) 40C
    #    method onto the new -20C one, preserving whatever limit is on file.
    jeta1 = FuelType.objects.filter(code="JETA1").first()
    visc_40 = TestMethod.objects.filter(code=VISC_40_CODE).first()
    if jeta1 is not None and visc_40 is not None:
        old_spec = SpecLimit.objects.filter(test_method=visc_40, fuel_type=jeta1).first()
        if old_spec is not None:
            SpecLimit.objects.get_or_create(
                test_method=visc_low,
                fuel_type=jeta1,
                defaults={"min_value": old_spec.min_value, "max_value": old_spec.max_value},
            )
            old_spec.delete()

    # 3. Straight numeric corrections.
    for fuel_code, test_code, new_min, new_max in NUMERIC_CORRECTIONS:
        fuel_type = FuelType.objects.filter(code=fuel_code).first()
        test_method = TestMethod.objects.filter(code=test_code).first()
        if fuel_type is None or test_method is None:
            continue
        spec, _created = SpecLimit.objects.get_or_create(
            test_method=test_method,
            fuel_type=fuel_type,
            defaults={"min_value": new_min, "max_value": new_max},
        )
        if not _created:
            spec.min_value = new_min
            spec.max_value = new_max
            spec.save(update_fields=["min_value", "max_value"])

    # 4. Add the missing Biodiesel Cetane Number requirement (D6751: >= 47).
    b100 = FuelType.objects.filter(code="B100").first()
    cetane = TestMethod.objects.filter(code=CETANE_CODE).first()
    if b100 is not None and cetane is not None:
        SpecLimit.objects.get_or_create(
            test_method=cetane, fuel_type=b100, defaults={"min_value": 47.0, "max_value": None}
        )


def revert_corrections(apps, schema_editor):
    FuelType = apps.get_model("catalog", "FuelType")
    TestMethod = apps.get_model("catalog", "TestMethod")
    SpecLimit = apps.get_model("catalog", "SpecLimit")

    # Restore the pre-audit numbers.
    reverse_map = [
        ("GAS95", "DIST10-D86", None, 70.0),
        ("GAS95", "DISTFBP-D86", None, 225.0),
        ("GAS91", "DIST10-D86", None, 70.0),
        ("GAS91", "DISTFBP-D86", None, 225.0),
        ("B100", "SULF-D5453", None, 10.0),
        ("B100", VISC_40_CODE, 3.5, 5.0),
        ("KERO", "SULF-D5453", None, 2000.0),
    ]
    for fuel_code, test_code, old_min, old_max in reverse_map:
        fuel_type = FuelType.objects.filter(code=fuel_code).first()
        test_method = TestMethod.objects.filter(code=test_code).first()
        if fuel_type is None or test_method is None:
            continue
        SpecLimit.objects.filter(test_method=test_method, fuel_type=fuel_type).update(
            min_value=old_min, max_value=old_max
        )

    # Move Jet A-1's viscosity spec back onto the 40C method and drop the
    # -20C one.
    jeta1 = FuelType.objects.filter(code="JETA1").first()
    visc_40 = TestMethod.objects.filter(code=VISC_40_CODE).first()
    visc_low = TestMethod.objects.filter(code=VISC_LOW_CODE).first()
    if jeta1 is not None and visc_40 is not None and visc_low is not None:
        low_spec = SpecLimit.objects.filter(test_method=visc_low, fuel_type=jeta1).first()
        if low_spec is not None:
            SpecLimit.objects.get_or_create(
                test_method=visc_40,
                fuel_type=jeta1,
                defaults={"min_value": low_spec.min_value, "max_value": low_spec.max_value},
            )
            low_spec.delete()
    if visc_low is not None:
        SpecLimit.objects.filter(test_method=visc_low).delete()
        visc_low.delete()

    # Drop the added Biodiesel cetane requirement.
    b100 = FuelType.objects.filter(code="B100").first()
    cetane = TestMethod.objects.filter(code=CETANE_CODE).first()
    if b100 is not None and cetane is not None:
        SpecLimit.objects.filter(test_method=cetane, fuel_type=b100).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0002_add_distillation_ibp"),
    ]

    operations = [
        migrations.RunPython(apply_corrections, revert_corrections),
    ]
