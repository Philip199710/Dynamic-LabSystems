"""The lab measures density at 20 °C, not 15 °C.

Renames the D1298 density test and converts every existing density spec
limit from 15 °C to 20 °C with the ASTM D1250 / API MPMS 11.1 (Table 54B)
thermal-expansion coefficients for generalized refined products.
Runs once; limits already on file are converted, report-only rows untouched.
"""

import math

from django.db import migrations


def _alpha(rho15):
    if rho15 >= 838.3:      # fuel oils
        return 186.9696 / rho15 ** 2 + 0.4862 / rho15
    if rho15 >= 787.5:      # jet fuels / kerosene
        return 594.5418 / rho15 ** 2
    if rho15 >= 770.4:      # transition zone
        return -0.00336312 + 2680.3206 / rho15 ** 2
    return 346.4228 / rho15 ** 2 + 0.4388 / rho15  # gasolines


def to_20c(rho15):
    a = _alpha(rho15)
    dt = 5.0
    return round(rho15 * math.exp(-a * dt * (1 + 0.8 * a * dt)), 1)


def forwards(apps, schema_editor):
    TestMethod = apps.get_model("catalog", "TestMethod")
    SpecLimit = apps.get_model("catalog", "SpecLimit")
    method = TestMethod.objects.filter(code="DENS-D1298").first()
    if method is None:
        return
    method.name = "Density at 20°C (Hydrometer)"
    method.description = "Density by hydrometer (ASTM D1298), measured and reported at 20 °C."
    method.save(update_fields=["name", "description"])
    for limit in SpecLimit.objects.filter(test_method=method):
        changed = False
        if limit.min_value is not None:
            limit.min_value = to_20c(limit.min_value)
            changed = True
        if limit.max_value is not None:
            limit.max_value = to_20c(limit.max_value)
            changed = True
        if changed:
            limit.save(update_fields=["min_value", "max_value"])


class Migration(migrations.Migration):
    dependencies = [("catalog", "0013_lubricants_and_brake_fluid")]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
