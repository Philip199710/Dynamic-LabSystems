import random
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from django.utils import timezone

from catalog.models import FuelType, Instrument, SpecLimit, TestMethod
from labtests.models import SampleTest, TestResult
from samples.models import Sample

User = get_user_model()


GROUP_PERMS = {
    "Lab Manager": "all",
    "QA": "all",
    "Analyst": ["samples", "labtests"],
    "Viewer": "view_only",
}

DEMO_USERS = [
    # username, password, first, last, is_staff, is_superuser, groups
    ("admin", "DynamicLab2026!", "Site", "Admin", True, True, ["Lab Manager"]),
    ("labmanager", "DynamicLab2026!", "Lena", "Ramirez", True, False, ["Lab Manager"]),
    ("qa1", "DynamicLab2026!", "Owen", "Silva", True, False, ["QA"]),
    ("analyst1", "DynamicLab2026!", "Mia", "Torres", False, False, ["Analyst"]),
    ("analyst2", "DynamicLab2026!", "Ken", "Osei", False, False, ["Analyst"]),
    ("viewer1", "DynamicLab2026!", "Guest", "Viewer", False, False, ["Viewer"]),
]

FUEL_TYPES = [
    ("Gasoline RON95", "GAS95", "Unleaded motor gasoline, RON 95."),
    ("Gasoline RON91", "GAS91", "Unleaded motor gasoline, RON 91."),
    ("Diesel (Automotive Gas Oil)", "DIESEL", "Automotive diesel fuel, ultra-low sulfur."),
    ("Jet A-1", "JETA1", "Aviation turbine fuel."),
    ("Biodiesel (B100/FAME)", "B100", "Fatty acid methyl ester biodiesel."),
    ("Kerosene", "KERO", "Illuminating/heating kerosene."),
]

# code, name, standard, unit
TEST_METHODS = [
    ("FLASH-D93", "Flash Point (Pensky-Martens Closed Cup)", "ASTM D93", "°C"),
    ("FLASH-D56", "Flash Point (Tag Closed Cup)", "ASTM D56", "°C"),
    ("DENS-D4052", "Density at 15°C", "ASTM D4052", "kg/m³"),
    ("SULF-D5453", "Sulfur Content (UV Fluorescence)", "ASTM D5453", "mg/kg"),
    ("DIST-D86", "Distillation, T95", "ASTM D86", "°C"),
    ("RVP-D5191", "Reid Vapor Pressure", "ASTM D5191", "kPa"),
    ("WATER-D6304", "Water Content (Karl Fischer)", "ASTM D6304", "mg/kg"),
    ("VISC-D445", "Kinematic Viscosity at 40°C", "ASTM D445", "mm²/s"),
    ("CETANE-D613", "Cetane Number", "ASTM D613", "—"),
    ("RON-D2699", "Research Octane Number", "ASTM D2699", "RON"),
    ("CLOUD-D2500", "Cloud Point", "ASTM D2500", "°C"),
]

# fuel_code -> {test_code: (min, max)}
SPEC_LIMITS = {
    "GAS95": {
        "RON-D2699": (95.0, None),
        "DENS-D4052": (720.0, 775.0),
        "SULF-D5453": (None, 10.0),
        "RVP-D5191": (45.0, 60.0),
    },
    "GAS91": {
        "RON-D2699": (91.0, None),
        "DENS-D4052": (715.0, 770.0),
        "SULF-D5453": (None, 10.0),
        "RVP-D5191": (45.0, 60.0),
    },
    "DIESEL": {
        "CETANE-D613": (51.0, None),
        "DENS-D4052": (820.0, 845.0),
        "SULF-D5453": (None, 10.0),
        "FLASH-D93": (55.0, None),
        "CLOUD-D2500": (None, 5.0),
        "VISC-D445": (2.0, 4.5),
        "WATER-D6304": (None, 200.0),
        "DIST-D86": (None, 360.0),
    },
    "JETA1": {
        "FLASH-D56": (38.0, None),
        "DENS-D4052": (775.0, 840.0),
        "SULF-D5453": (None, 3000.0),
        "VISC-D445": (None, 8.0),
    },
    "B100": {
        "DENS-D4052": (860.0, 900.0),
        "FLASH-D93": (93.0, None),
        "SULF-D5453": (None, 10.0),
        "WATER-D6304": (None, 500.0),
        "VISC-D445": (3.5, 5.0),
    },
    "KERO": {
        "FLASH-D56": (38.0, None),
        "DENS-D4052": (775.0, 840.0),
        "SULF-D5453": (None, 2000.0),
    },
}

INSTRUMENTS = [
    ("Gas Chromatograph GC-2010", "Gas Chromatograph", "GC2010-004", -5),
    ("Densitometer DMA 4500", "Densitometer", "DMA4500-011", 40),
    ("Pensky-Martens Flash Point Tester", "Flash Point Tester", "PM-93-002", 20),
    ("Karl Fischer Titrator", "Titrator", "KF-6304-007", 90),
    ("Automatic Distillation Unit", "Distillation Unit", "AD-86-003", 150),
    ("Viscometer Bath", "Viscometer", "VB-445-009", 60),
]


class Command(BaseCommand):
    help = "Seed Dynamic LabSystems with demo groups, users, catalog, and sample data."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Delete existing demo data before seeding.")

    def handle(self, *args, **options):
        if options["reset"]:
            self.stdout.write("Clearing existing data...")
            TestResult.objects.all().delete()
            SampleTest.objects.all().delete()
            Sample.objects.all().delete()
            SpecLimit.objects.all().delete()
            TestMethod.objects.all().delete()
            FuelType.objects.all().delete()
            Instrument.objects.all().delete()

        self.seed_groups()
        users = self.seed_users()
        fuel_types = self.seed_fuel_types()
        test_methods = self.seed_test_methods()
        self.seed_spec_limits(fuel_types, test_methods)
        self.seed_instruments()
        self.seed_samples(fuel_types, test_methods, users)

        self.stdout.write(self.style.SUCCESS("Demo data seeded."))
        self.stdout.write("Login with any of:")
        for username, password, *_ in DEMO_USERS:
            self.stdout.write(f"  {username} / {password}")

    def seed_groups(self):
        for name in GROUP_PERMS:
            Group.objects.get_or_create(name=name)

        def perms_for(app_labels, actions):
            cts = ContentType.objects.filter(app_label__in=app_labels)
            return Permission.objects.filter(content_type__in=cts, codename__regex=r"^(" + "|".join(actions) + r")_")

        all_apps = ["catalog", "samples", "labtests", "reports"]
        full_actions = ["add", "change", "delete", "view"]

        lab_manager = Group.objects.get(name="Lab Manager")
        lab_manager.permissions.set(perms_for(all_apps, full_actions))

        qa = Group.objects.get(name="QA")
        qa.permissions.set(perms_for(all_apps, full_actions))

        analyst = Group.objects.get(name="Analyst")
        analyst.permissions.set(perms_for(["samples", "labtests"], ["add", "change", "view"]))

        viewer = Group.objects.get(name="Viewer")
        viewer.permissions.set(perms_for(all_apps, ["view"]))

    def seed_users(self):
        users = {}
        for username, password, first, last, is_staff, is_superuser, groups in DEMO_USERS:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    "first_name": first,
                    "last_name": last,
                    "is_staff": is_staff,
                    "is_superuser": is_superuser,
                    "email": f"{username}@dynamiclabsystems.example",
                },
            )
            if created:
                user.set_password(password)
                user.is_staff = is_staff
                user.is_superuser = is_superuser
                user.save()
            user.groups.set(Group.objects.filter(name__in=groups))
            users[username] = user
        return users

    def seed_fuel_types(self):
        fuel_types = {}
        for name, code, desc in FUEL_TYPES:
            ft, _ = FuelType.objects.get_or_create(code=code, defaults={"name": name, "description": desc})
            fuel_types[code] = ft
        return fuel_types

    def seed_test_methods(self):
        methods = {}
        for code, name, standard, unit in TEST_METHODS:
            tm, _ = TestMethod.objects.get_or_create(
                code=code, defaults={"name": name, "standard_reference": standard, "unit": unit}
            )
            methods[code] = tm
        return methods

    def seed_spec_limits(self, fuel_types, test_methods):
        for fuel_code, specs in SPEC_LIMITS.items():
            for test_code, (min_v, max_v) in specs.items():
                SpecLimit.objects.get_or_create(
                    fuel_type=fuel_types[fuel_code],
                    test_method=test_methods[test_code],
                    defaults={"min_value": min_v, "max_value": max_v},
                )

    def seed_instruments(self):
        today = timezone.localdate()
        for name, itype, serial, days_offset in INSTRUMENTS:
            Instrument.objects.get_or_create(
                serial_number=serial,
                defaults={
                    "name": name,
                    "instrument_type": itype,
                    "location": "Main lab",
                    "calibration_due_date": today + timedelta(days=days_offset),
                },
            )

    def seed_samples(self, fuel_types, test_methods, users):
        if Sample.objects.exists():
            self.stdout.write("Samples already exist — skipping demo sample creation.")
            return

        analyst_names = ["analyst1", "analyst2"]
        sources = ["Terminal A storage tank", "Refinery batch QC", "Retail station #14", "Import cargo survey", "Blending plant"]
        random.seed(7)
        today = timezone.localdate()

        plan = [
            ("GAS95", "COMPLETE", -12),
            ("DIESEL", "COMPLETE", -9),
            ("DIESEL", "COMPLETE", -7),
            ("JETA1", "IN_TESTING", -4),
            ("B100", "IN_TESTING", -3),
            ("GAS91", "RECEIVED", -1),
            ("KERO", "RECEIVED", 0),
            ("DIESEL", "IN_TESTING", -2),
        ]

        # Index of the plan entry that should get one deliberately out-of-spec
        # result, so the dashboard/analytics demo shows a real fail case.
        OUT_OF_SPEC_PLAN_INDEX = 2  # the second DIESEL / COMPLETE sample

        for plan_index, (fuel_code, target_status, received_offset) in enumerate(plan):
            ft = fuel_types[fuel_code]
            sample = Sample(
                fuel_type=ft,
                source=random.choice(sources),
                date_received=today + timedelta(days=received_offset),
                received_by=users["labmanager"],
                storage_location=f"Rack {random.randint(1, 8)}",
            )
            sample.save()
            sample.log(users["labmanager"], "Sample received", notes=f"Source: {sample.source}")

            applicable_tests = list(SPEC_LIMITS.get(fuel_code, {}).keys())
            n_tests = len(applicable_tests) if target_status != "RECEIVED" else 0

            for i, test_code in enumerate(applicable_tests[:n_tests]):
                tm = test_methods[test_code]
                analyst = users[analyst_names[i % 2]]
                due = sample.date_received + timedelta(days=3)
                st = SampleTest.objects.create(sample=sample, test_method=tm, assigned_to=analyst, due_date=due)
                st.assign(users["labmanager"])

                give_result = target_status == "COMPLETE" or (target_status == "IN_TESTING" and i % 2 == 0)
                if give_result:
                    min_v, max_v = SPEC_LIMITS[fuel_code][test_code]
                    force_fail = plan_index == OUT_OF_SPEC_PLAN_INDEX and i == 0
                    value = self._plausible_value(min_v, max_v, out_of_spec=force_fail)
                    result = TestResult(sample_test=st, value=value, entered_by=analyst)
                    result.record(analyst)

            sample.recompute_status()

    @staticmethod
    def _plausible_value(min_v, max_v, out_of_spec=False):
        if min_v is not None and max_v is not None:
            span = max_v - min_v
            value = random.uniform(min_v + span * 0.2, max_v - span * 0.2)
            if out_of_spec:
                value = max_v + span * 0.15
        elif min_v is not None:
            value = min_v + abs(min_v) * 0.05 + random.uniform(0, max(1.0, abs(min_v) * 0.1))
            if out_of_spec:
                value = min_v - abs(min_v) * 0.05
        elif max_v is not None:
            value = max_v - abs(max_v) * 0.15 - random.uniform(0, max(1.0, abs(max_v) * 0.1))
            if out_of_spec:
                value = max_v + abs(max_v) * 0.2
        else:
            value = round(random.uniform(1, 100), 2)
        return round(value, 2)
