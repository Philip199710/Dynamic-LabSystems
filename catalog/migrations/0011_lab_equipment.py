"""Register the lab's actual equipment and make sure every ASTM method it runs
is in the catalog (with the standard spec limits), whether or not demo data was
ever seeded on this database. Safe to re-run: it only creates what's missing and
never overwrites limits or instruments that already exist."""

from django.db import migrations

METHODS = {
    # code: (name, standard, unit)
    "WATER-D6304": ("Water Content (Karl Fischer)", "ASTM D6304", "mg/kg"),
    "SED-D473": ("Sediment (Extraction Method)", "ASTM D473", "% mass"),
    "DENS-D1298": ("Density at 15°C (Hydrometer)", "ASTM D1298", "kg/m³"),
    "FLASH-D93": ("Flash Point (Pensky-Martens Closed Cup)", "ASTM D93", "°C"),
    "FREEZE-D2386": ("Freezing Point", "ASTM D2386", "°C"),
    "COND-D2624": ("Electrical Conductivity", "ASTM D2624", "pS/m"),
    "DIST-IBP-D86": ("Distillation, Initial Boiling Point (IBP)", "ASTM D86", "°C"),
    "DIST10-D86": ("Distillation, 10% Recovered", "ASTM D86", "°C"),
    "DIST-D86": ("Distillation, T95", "ASTM D86", "°C"),
    "DISTFBP-D86": ("Distillation, Final Boiling Point", "ASTM D86", "°C"),
}

# Standard acceptance limits per fuel type (min, max); None = no bound.
# Only added where the fuel type exists and no limit is on file yet.
SPEC_LIMITS = {
    "WATER-D6304": {"AVGAS100LL": (None, None), "B100": (None, 500.0), "DIESEL": (None, 200.0), "GAS91": (None, 100.0),
                    "GAS95": (None, 100.0), "JETA1": (None, None), "KERO": (None, None), "LPG": (None, None), "MGO": (None, None)},
    "SED-D473": {"B100": (None, 0.01), "DIESEL": (None, 0.01), "KERO": (None, None), "MARINE-HFO": (None, None), "MGO": (None, 0.01)},
    "DENS-D1298": {"B100": (860.0, 900.0), "DIESEL": (820.0, 845.0), "GAS91": (715.0, 770.0), "GAS95": (720.0, 775.0),
                   "JETA1": (775.0, 840.0), "KERO": (775.0, 840.0)},
    "FLASH-D93": {"B100": (93.0, None), "CRUDE": (None, None), "DIESEL": (55.0, None), "MARINE-HFO": (60.0, None), "MGO": (60.0, None)},
    "FREEZE-D2386": {"AVGAS100LL": (None, -58.0), "JETA1": (None, -47.0)},
    "COND-D2624": {"AVGAS100LL": (None, None), "B100": (None, None), "DIESEL": (25.0, None), "GAS91": (None, None), "GAS95": (None, None),
                   "JETA1": (50.0, 600.0), "KERO": (None, None), "MARINE-HFO": (None, None), "MGO": (None, None)},
    "DIST-IBP-D86": {"DIESEL": (160.0, 200.0), "GAS91": (30.0, 45.0), "GAS95": (30.0, 45.0), "JETA1": (150.0, 170.0), "KERO": (150.0, 175.0)},
    "DIST10-D86": {"GAS91": (None, 50.0), "GAS95": (None, 50.0), "JETA1": (None, 205.0), "KERO": (None, 205.0)},
    "DIST-D86": {"DIESEL": (None, 360.0)},
    "DISTFBP-D86": {"DIESEL": (340.0, 370.0), "GAS91": (None, 210.0), "GAS95": (None, 210.0), "JETA1": (None, 300.0), "KERO": (None, 300.0)},
}

# model, name, measurement (type), property tested, temperature range, method codes, method note
EQUIPMENT = [
    ("KFT-40VC", "KFT-40VC Karl Fischer Titrator", "Water content", "Moisture (ppm–mg)", "Room temperature",
     ["WATER-D6304"], "Karl Fischer (volumetric/coulometric)"),
    ("AWD-33", "AWD-33 Sediment Tester", "Sediment", "Solid impurities", "",
     ["SED-D473"], "ASTM D473 (extraction)"),
    ("AWD-18A", "AWD-18A Density Tester", "Density", "Mass/volume", "Room temperature – 100°C",
     ["DENS-D1298"], "ASTM D1298"),
    ("AWD-02", "AWD-02 Flash Point Tester", "Flash point", "Ignition safety", "Ambient – heated",
     ["FLASH-D93"], "ASTM D93 (closed cup)"),
    ("AWD-1803", "AWD-1803 Freezing Point Tester", "Freezing point", "Cold-flow / crystallization", "Ambient to -70°C",
     ["FREEZE-D2386"], "ASTM D2386"),
    ("Model 1152", "Model 1152 Conductivity Meter", "Conductivity", "Static charge dissipation", "0–75°C",
     ["COND-D2624"], "ASTM D2624"),
    ("AWD-05C", "AWD-05C Distillation Tester", "Distillation range", "Volatility", "Ambient – 80°C (condenser)",
     ["DIST-IBP-D86", "DIST10-D86", "DIST-D86", "DISTFBP-D86"], "ASTM D86"),
]


def forwards(apps, schema_editor):
    TestMethod = apps.get_model("catalog", "TestMethod")
    FuelType = apps.get_model("catalog", "FuelType")
    SpecLimit = apps.get_model("catalog", "SpecLimit")
    Instrument = apps.get_model("catalog", "Instrument")

    methods = {}
    for code, (name, standard, unit) in METHODS.items():
        tm, created = TestMethod.objects.get_or_create(
            code=code, defaults={"name": name, "standard_reference": standard, "unit": unit, "active": True}
        )
        if not created and not tm.active:
            tm.active = True
            tm.save(update_fields=["active"])
        methods[code] = tm

    fuels = {f.code: f for f in FuelType.objects.all()}
    for code, limits in SPEC_LIMITS.items():
        for fuel_code, (lo, hi) in limits.items():
            fuel = fuels.get(fuel_code)
            if fuel is not None:
                SpecLimit.objects.get_or_create(
                    test_method=methods[code], fuel_type=fuel, defaults={"min_value": lo, "max_value": hi}
                )

    for model, name, measurement, prop, temp, codes, standard_note in EQUIPMENT:
        instrument = Instrument.objects.filter(model_number=model).first()
        if instrument is None:
            instrument = Instrument.objects.create(
                name=name,
                model_number=model,
                instrument_type=measurement,
                temperature_range=temp,
                status="ACTIVE",
                notes=f"Property tested: {prop}. Method: {standard_note}.",
            )
        instrument.test_methods.add(*[methods[c] for c in codes])


class Migration(migrations.Migration):
    dependencies = [("catalog", "0010_instrument_model_and_methods")]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
