# Data migration: add four internationally-recognised fuel types requested
# by name — Marine Fuel Oil (residual/HSFO), Marine Gas Oil, LPG/Autogas, and
# Avgas 100LL — each with test methods and spec limits sourced from their
# real governing standards (ISO 8217:2017, EN 589:2024, ASTM D910/DEF STAN
# 91-90). Six new test methods are added because the existing ones use the
# wrong test condition or apparatus for these fuels (see comments in
# seed_demo.py for the full reasoning and sources behind every number here).
from django.db import migrations

FUEL_TYPES = [
    ("Marine Fuel Oil (RMG 380 / HSFO)", "MARINE-HFO", "Residual marine bunker fuel, ISO 8217 grade ISO-F-RMG 380."),
    ("Marine Gas Oil (DMA)", "MGO", "Distillate marine bunker fuel, ISO 8217 grade ISO-F-DMA."),
    ("LPG / Autogas", "LPG", "Liquefied petroleum gas for automotive/cylinder use, per EN 589."),
    ("Aviation Gasoline (Avgas 100LL)", "AVGAS100LL", "Leaded piston-engine aviation fuel, per ASTM D910 / DEF STAN 91-90."),
]

TEST_METHODS = [
    ("VISC-D445-50", "Kinematic Viscosity at 50°C", "ASTM D445", "mm²/s"),
    ("WATER-D95", "Water Content (Distillation Method)", "ASTM D95", "% vol"),
    ("VAPOR-D1267", "Vapor Pressure (LPG)", "ASTM D1267", "kPa"),
    ("MON-D2700", "Motor Octane Number", "ASTM D2700", "MON"),
    ("HEAT-D3338", "Net Heat of Combustion", "ASTM D3338", "MJ/kg"),
    ("TEL-D3341", "Tetraethyl Lead Content", "ASTM D3341", "g Pb/L"),
]

# fuel_code -> {test_code: (min, max)}
SPEC_LIMITS = {
    "MARINE-HFO": {
        "VISC-D445-50": (None, 380.0),
        "DENS-D4052": (None, 1010.0),
        "WATER-D95": (None, 0.50),
        "FLASH-D93": (60.0, None),
        "SULF-D5453": (None, 5000.0),
    },
    "MGO": {
        "DENS-D4052": (None, 890.0),
        "VISC-D445": (2.0, 6.0),
        "FLASH-D93": (60.0, None),
        "CETANE-D613": (40.0, None),
        "SULF-D5453": (None, 1000.0),
        "WATER-D6304": (None, None),
    },
    "LPG": {
        "VAPOR-D1267": (None, 1550.0),
        "SULF-D5453": (None, 30.0),
        "DENS-D4052": (None, None),
    },
    "AVGAS100LL": {
        "FREEZE-D2386": (None, -58.0),
        "SULF-D5453": (None, 500.0),
        "MON-D2700": (99.6, None),
        "RVP-D5191": (38.0, 49.0),
        "HEAT-D3338": (43.5, None),
        "TEL-D3341": (None, 0.56),
    },
}


def add_fuel_types(apps, schema_editor):
    FuelType = apps.get_model("catalog", "FuelType")
    TestMethod = apps.get_model("catalog", "TestMethod")
    SpecLimit = apps.get_model("catalog", "SpecLimit")

    for name, code, desc in FUEL_TYPES:
        FuelType.objects.get_or_create(code=code, defaults={"name": name, "description": desc})

    for code, name, standard, unit in TEST_METHODS:
        TestMethod.objects.get_or_create(
            code=code, defaults={"name": name, "standard_reference": standard, "unit": unit}
        )

    for fuel_code, specs in SPEC_LIMITS.items():
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


def remove_fuel_types(apps, schema_editor):
    FuelType = apps.get_model("catalog", "FuelType")
    TestMethod = apps.get_model("catalog", "TestMethod")

    fuel_codes = [code for _, code, _ in FUEL_TYPES]
    FuelType.objects.filter(code__in=fuel_codes).delete()  # cascades to SpecLimit

    test_codes = [code for code, _, _, _ in TEST_METHODS]
    for code in test_codes:
        tm = TestMethod.objects.filter(code=code).first()
        if tm is not None and not tm.spec_limits.exists():
            tm.delete()


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0003_international_standard_corrections"),
    ]

    operations = [
        migrations.RunPython(add_fuel_types, remove_fuel_types),
    ]
