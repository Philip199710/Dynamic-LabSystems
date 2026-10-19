"""Spec ranges for the lab's four main products, for every test the lab's seven
instruments run. (min, max); None = no bound. A test with no limit in the
product spec is stored with both bounds empty: it can still be assigned and
recorded, the result is reported without a pass/fail verdict.

Sources (summary limits):
  Jet A-1   DEF STAN 91-091 / ASTM D1655
  Diesel    EN 590 (AGO), conductivity per ASTM D975
  Petrol    EN 228 (density, distillation)
  Kerosene  ASTM D3699 (dual-purpose kerosene)
"""

from django.db import migrations

FUELS = {
    "JETA1": "Jet A-1",
    "DIESEL": "Diesel (Automotive Gas Oil)",
    "GAS95": "Gasoline RON95",
    "GAS91": "Gasoline RON91",
    "KERO": "Kerosene",
}

PETROL = {
    "DENS-D1298": (720.0, 775.0),     # kg/m³ at 15 °C
    "FLASH-D93": (None, None),        # not applicable to petrol (below ambient)
    "WATER-D6304": (None, None),      # report
    "SED-D473": (None, None),         # report
    "FREEZE-D2386": (None, None),     # not applicable
    "COND-D2624": (None, None),       # report
    "DIST-IBP-D86": (None, None),     # report
    "DIST10-D86": (None, 70.0),       # °C max
    "DIST-D86": (None, None),         # report
    "DISTFBP-D86": (None, 210.0),     # °C max
}

LIMITS = {
    "JETA1": {
        "DENS-D1298": (775.0, 840.0),
        "FLASH-D93": (38.0, None),
        "WATER-D6304": (None, None),
        "SED-D473": (None, None),
        "FREEZE-D2386": (None, -47.0),
        "COND-D2624": (50.0, 600.0),
        "DIST-IBP-D86": (None, None),
        "DIST10-D86": (None, 205.0),
        "DIST-D86": (None, None),
        "DISTFBP-D86": (None, 300.0),
    },
    "DIESEL": {
        "DENS-D1298": (820.0, 845.0),
        "FLASH-D93": (55.0, None),
        "WATER-D6304": (None, 200.0),
        "SED-D473": (None, 0.01),
        "FREEZE-D2386": (None, None),
        "COND-D2624": (25.0, None),
        "DIST-IBP-D86": (None, None),
        "DIST10-D86": (None, None),
        "DIST-D86": (None, 360.0),
        "DISTFBP-D86": (None, None),
    },
    "GAS95": PETROL,
    "GAS91": PETROL,
    "KERO": {
        "DENS-D1298": (775.0, 840.0),
        "FLASH-D93": (38.0, None),
        "WATER-D6304": (None, None),
        "SED-D473": (None, None),
        "FREEZE-D2386": (None, -30.0),
        "COND-D2624": (None, None),
        "DIST-IBP-D86": (None, None),
        "DIST10-D86": (None, 205.0),
        "DIST-D86": (None, None),
        "DISTFBP-D86": (None, 300.0),
    },
}


def forwards(apps, schema_editor):
    FuelType = apps.get_model("catalog", "FuelType")
    TestMethod = apps.get_model("catalog", "TestMethod")
    SpecLimit = apps.get_model("catalog", "SpecLimit")
    methods = {m.code: m for m in TestMethod.objects.filter(code__in=PETROL.keys())}
    for code, name in FUELS.items():
        fuel, _ = FuelType.objects.get_or_create(code=code, defaults={"name": name})
        for method_code, (lo, hi) in LIMITS[code].items():
            method = methods.get(method_code)
            if method is not None:
                SpecLimit.objects.update_or_create(
                    test_method=method, fuel_type=fuel, defaults={"min_value": lo, "max_value": hi}
                )


class Migration(migrations.Migration):
    dependencies = [("catalog", "0011_lab_equipment")]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
