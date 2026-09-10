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
    ("Marine Fuel Oil (RMG 380 / HSFO)", "MARINE-HFO", "Residual marine bunker fuel, ISO 8217 grade ISO-F-RMG 380."),
    ("Marine Gas Oil (DMA)", "MGO", "Distillate marine bunker fuel, ISO 8217 grade ISO-F-DMA."),
    ("LPG / Autogas", "LPG", "Liquefied petroleum gas for automotive/cylinder use, per EN 589."),
    ("Aviation Gasoline (Avgas 100LL)", "AVGAS100LL", "Leaded piston-engine aviation fuel, per ASTM D910 / DEF STAN 91-90."),
    (
        "Crude Oil",
        "CRUDE",
        "Unrefined crude petroleum — characterized/assayed, not graded against a fixed pass/fail "
        "spec the way a finished fuel is (different crude streams, e.g. WTI/Brent/Dubai/Maya, have "
        "very different 'normal' values for the same property, none of them 'out of spec'). Its "
        "test methods below are recorded for the assay report, not scored against a min/max.",
    ),
]

# code, name, standard, unit
TEST_METHODS = [
    ("FLASH-D93", "Flash Point (Pensky-Martens Closed Cup)", "ASTM D93", "°C"),
    ("FLASH-D56", "Flash Point (Tag Closed Cup)", "ASTM D56", "°C"),
    ("DENS-D4052", "Density at 15°C", "ASTM D4052", "kg/m³"),
    ("SULF-D5453", "Sulfur Content (UV Fluorescence)", "ASTM D5453", "mg/kg"),
    ("DIST-D86", "Distillation, T95", "ASTM D86", "°C"),
    ("DIST-IBP-D86", "Distillation, Initial Boiling Point (IBP)", "ASTM D86", "°C"),
    ("RVP-D5191", "Reid Vapor Pressure", "ASTM D5191", "kPa"),
    ("WATER-D6304", "Water Content (Karl Fischer)", "ASTM D6304", "mg/kg"),
    ("VISC-D445", "Kinematic Viscosity at 40°C", "ASTM D445", "mm²/s"),
    # Jet A-1's viscosity limit (DEF STAN 91-091 / ASTM D1655) is measured at
    # -20°C, not 40°C — a distinct method so the recorded test condition is
    # accurate, not just a relabeled version of the 40°C fuel-oil test.
    ("VISC-D445-LOW", "Kinematic Viscosity at -20°C", "ASTM D445", "mm²/s"),
    ("CETANE-D613", "Cetane Number", "ASTM D613", "—"),
    ("RON-D2699", "Research Octane Number", "ASTM D2699", "RON"),
    ("CLOUD-D2500", "Cloud Point", "ASTM D2500", "°C"),
    # Added for aviation-fuel QC coverage and a manual/reference density
    # method, plus a sediment/particulate check for blended distillates —
    # see the ASTM standard references below for scope of each.
    ("DENS-D1298", "Density at 15°C (Hydrometer)", "ASTM D1298", "kg/m³"),
    ("SED-D473", "Sediment (Extraction Method)", "ASTM D473", "% mass"),
    ("FREEZE-D2386", "Freezing Point", "ASTM D2386", "°C"),
    ("COND-D2624", "Electrical Conductivity", "ASTM D2624", "pS/m"),
    ("DIST10-D86", "Distillation, 10% Recovered", "ASTM D86", "°C"),
    ("DISTFBP-D86", "Distillation, Final Boiling Point", "ASTM D86", "°C"),
    # Added for the new marine/LPG/avgas fuel types — each is a genuinely
    # distinct international method, not a relabeled version of an existing
    # one, because the test condition or apparatus actually differs:
    #  - Residual marine fuel viscosity is graded at 50C (ISO 3104), not 40C.
    ("VISC-D445-50", "Kinematic Viscosity at 50°C", "ASTM D445", "mm²/s"),
    #  - Water in dark residual fuel oil is read by distillation (Dean-Stark),
    #    not Karl Fischer — Karl Fischer titration is unreliable on fuels
    #    with this much colour/particulate.
    ("WATER-D95", "Water Content (Distillation Method)", "ASTM D95", "% vol"),
    #  - LPG's vapour pressure is measured on liquefied gas via the
    #    LP-Gas method, not the D5191 mini-method built for gasoline.
    ("VAPOR-D1267", "Vapor Pressure (LPG)", "ASTM D1267", "kPa"),
    #  - Avgas is graded by Motor Octane Number (Motor Method), not the
    #    Research Method (RON-D2699) used for automotive gasoline.
    ("MON-D2700", "Motor Octane Number", "ASTM D2700", "MON"),
    ("HEAT-D3338", "Net Heat of Combustion", "ASTM D3338", "MJ/kg"),
    ("TEL-D3341", "Tetraethyl Lead Content", "ASTM D3341", "g Pb/L"),
    # Crude oil assay methods — crude has its own dedicated international
    # standards distinct from finished-fuel testing (different apparatus,
    # different reporting units/conventions):
    ("API-D287", "API Gravity", "ASTM D287", "°API"),
    ("BSW-D4007", "Water and Sediment (BS&W)", "ASTM D4007", "% vol"),
    # Reported in the crude-trading industry's native unit, not converted to
    # mg/kg, so results are directly comparable to cargo/assay paperwork.
    ("SALT-D3230", "Salt Content", "ASTM D3230", "PTB"),
    # The dissolved gas in live crude makes D323 (Reid Method, built for
    # finished products) unreliable — D6377 is the method actually used for
    # crude oil vapor pressure.
    ("VAPOR-D6377", "Vapor Pressure, Crude Oil (VPCRx)", "ASTM D6377", "kPa"),
    ("POUR-D97", "Pour Point", "ASTM D97", "°C"),
    ("TAN-D664", "Total Acid Number (TAN)", "ASTM D664", "mg KOH/g"),
    ("H2S-D7621", "Hydrogen Sulfide Content", "ASTM D7621", "mg/kg"),
    # Crude's sulfur is normally read by X-ray fluorescence (D4294), not the
    # UV-fluorescence method (D5453) used for the much-lower ppm levels in
    # finished fuels, and is reported as % mass, not mg/kg, to match how
    # crude assays (e.g. "sweet" vs. "sour") are actually quoted.
    ("SULF-D4294", "Sulfur Content (X-ray Fluorescence)", "ASTM D4294", "% mass"),
    # Jet A-1's particulate-matter check is a dedicated line-sampling method
    # (DEF STAN 91-091 cites D2276/D5452/IP423 interchangeably) reported in
    # mg/L — a different apparatus and unit than the extraction-based D473
    # sediment test used on heavier fuel oils, so it gets its own code.
    ("PART-D2276", "Particulate Matter Content", "ASTM D2276", "mg/L"),
    # Crude oil's distillation curve is run under vacuum/at multiple cuts
    # (True Boiling Point analysis) rather than a single atmospheric D86
    # run — a genuinely different method from every other distillation
    # entry in this catalog.
    ("DIST-D2892", "Distillation, True Boiling Point (TBP)", "ASTM D2892", "°C"),
]

# fuel_code -> {test_code: (min, max)}
SPEC_LIMITS = {
    "GAS95": {
        "RON-D2699": (95.0, None),
        "DENS-D4052": (720.0, 775.0),
        "SULF-D5453": (None, 10.0),
        "RVP-D5191": (45.0, 60.0),
        # D1298 is the manual-hydrometer equivalent of D4052 — same
        # physical property, same acceptance range.
        "DENS-D1298": (720.0, 775.0),
        # EN 228 (widely followed across Europe/Asia-Pacific, incl. RON-graded
        # markets like Thailand): T10 <= 50C, FBP <= 210C.
        "DIST10-D86": (None, 50.0),
        "DISTFBP-D86": (None, 210.0),
        # EN 228 doesn't fix an IBP number (only T10/E-points/FBP are
        # graded) — this is the typical real-world operating range reported
        # on gasoline certificates of quality, not an EN 228 pass/fail limit.
        "DIST-IBP-D86": (30.0, 45.0),
        # Gasoline's flash point is a fixed physical property of such a
        # volatile fuel (well below ambient) — EN 228/ASTM D4814 don't grade
        # it as a pass/fail spec (RVP governs volatility instead). Typical
        # SDS-reported range for finished motor gasoline, informational only.
        "FLASH-D56": (-45.0, -20.0),
        # EN 228 sets no numeric water content — only a visual "clear and
        # bright, free from water" requirement. Typical trace figure some
        # labs track informationally, not an EN 228 pass/fail number.
        "WATER-D6304": (None, 100.0),
        # No universal conductivity spec for motor gasoline (unlike Jet
        # A-1's mandatory static-dissipator range) — recorded only where a
        # static-dissipator additive is dosed for pipeline/terminal safety.
        "COND-D2624": (None, None),
        # EN 228 sets no numeric sediment/particulate limit for gasoline.
        # Typical trace figure, informational only.
        "SED-D473": (None, 0.01),
    },
    "GAS91": {
        "RON-D2699": (91.0, None),
        "DENS-D4052": (715.0, 770.0),
        "SULF-D5453": (None, 10.0),
        "RVP-D5191": (45.0, 60.0),
        "DENS-D1298": (715.0, 770.0),
        "DIST10-D86": (None, 50.0),
        "DISTFBP-D86": (None, 210.0),
        "DIST-IBP-D86": (30.0, 45.0),
        "FLASH-D56": (-45.0, -20.0),
        "WATER-D6304": (None, 100.0),
        "COND-D2624": (None, None),
        "SED-D473": (None, 0.01),
    },
    # EN 590 (European automotive diesel standard, widely followed across
    # Asia-Pacific export/import markets) — every limit below matches EN 590
    # exactly, which is why the cetane/sulfur numbers read tighter than the
    # (looser) US ASTM D975 No. 2-D minimums.
    "DIESEL": {
        "CETANE-D613": (51.0, None),
        "DENS-D4052": (820.0, 845.0),
        "SULF-D5453": (None, 10.0),
        "FLASH-D93": (55.0, None),
        "CLOUD-D2500": (None, 5.0),
        "VISC-D445": (2.0, 4.5),
        "WATER-D6304": (None, 200.0),
        "DIST-D86": (None, 360.0),
        "DENS-D1298": (820.0, 845.0),
        # Sediment/particulate contamination screen for AGO handling & storage.
        "SED-D473": (None, 0.01),
        # Neither EN 590 nor ASTM D975 grades diesel's IBP/FBP (only T95 is
        # an official limit, above) — these are typical real-world ranges
        # from refinery/ULSD certificates of quality, not a regulatory
        # pass/fail band.
        "DIST-IBP-D86": (160.0, 200.0),
        "DISTFBP-D86": (340.0, 370.0),
        # Not an EN 590 number itself — common terminal/pipeline practice for
        # static-safety during switch-loading (min conductivity so charge
        # dissipates rather than building up). Informational.
        "COND-D2624": (25.0, None),
    },
    "JETA1": {
        "FLASH-D56": (38.0, None),
        "DENS-D4052": (775.0, 840.0),
        "SULF-D5453": (None, 3000.0),
        # Jet A-1 viscosity is specified at -20C, not the 40C fuel-oil
        # condition — see VISC-D445-LOW above.
        "VISC-D445-LOW": (None, 8.0),
        "DENS-D1298": (775.0, 840.0),
        # DEF STAN 91-091 / ASTM D1655 Jet A-1 limits.
        "FREEZE-D2386": (None, -47.0),
        "COND-D2624": (50.0, 600.0),
        "DIST10-D86": (None, 205.0),
        "DISTFBP-D86": (None, 300.0),
        # DEF STAN/D1655 don't grade Jet A-1's IBP — this is the typical
        # real-world range from Jet A-1 certificates of quality.
        "DIST-IBP-D86": (150.0, 170.0),
        # DEF STAN 91-091/D1655 don't set a numeric water content limit —
        # water is controlled by coalescer filtration and checked with a
        # free-water detector / Microseparometer rating, not graded by KF
        # ppm. Recorded for trend monitoring only.
        "WATER-D6304": (None, None),
        # DEF STAN 91-091 particulate matter limit at point of manufacture
        # (line-sampling method) — real published figure, not typical/range.
        "PART-D2276": (None, 1.0),
    },
    # ASTM D6751 (flash point, viscosity, cetane) blended with EN 14214
    # (water content, density — the European biodiesel standard, also
    # widely followed across Asia-Pacific) — a common real-world combination
    # for a blend stock destined for both markets.
    #
    # Deliberately NO ASTM D86 (atmospheric distillation) entries here: FAME
    # esters boil far higher (~330-350C) than D86's atmospheric-pressure
    # range can measure without decomposing the sample. D6751 doesn't
    # require or even permit a D86 IBP/FBP for B100 — biodiesel's boiling
    # range, when tested at all, is measured by ASTM D1160 (distillation at
    # reduced pressure) or D7398 (GC simulated distillation), not D86. So
    # unlike every other fuel type here, B100 has no distillation entry —
    # that's correct, not a missing spec.
    "B100": {
        "DENS-D4052": (860.0, 900.0),
        "FLASH-D93": (93.0, None),
        # D6751 "S15" blending grade (<=15 mg/kg) — the sulfur cap required
        # so the blended finished diesel can still meet its own <=10 mg/kg
        # (EN 590) or <=15 mg/kg (US S15) limit.
        "SULF-D5453": (None, 15.0),
        "WATER-D6304": (None, 500.0),
        # Full ASTM D6751 allowable range; not narrowed to an internal target.
        "VISC-D445": (1.9, 6.0),
        "CETANE-D613": (47.0, None),
        "DENS-D1298": (860.0, 900.0),
        "SED-D473": (None, 0.01),
        # No biodiesel conductivity spec on file. Recorded only.
        "COND-D2624": (None, None),
    },
    # ASTM D3699 No. 1-K (higher-quality illuminating/heating grade — matches
    # this fuel type's own description) plus DEF STAN/D1655-derived
    # distillation points shared with Jet A-1's similar boiling range.
    "KERO": {
        "FLASH-D56": (38.0, None),
        "DENS-D4052": (775.0, 840.0),
        # No. 1-K grade: <=0.04% mass = 400 mg/kg (No. 2-K would be <=3000).
        "SULF-D5453": (None, 400.0),
        "DENS-D1298": (775.0, 840.0),
        "DIST10-D86": (None, 205.0),
        "DISTFBP-D86": (None, 300.0),
        # D3699 doesn't fix Kerosene's IBP either — typical range, sharing
        # a similar boiling profile to Jet A-1/kerosene-type fuel.
        "DIST-IBP-D86": (150.0, 175.0),
        # D3699 sets no numeric water content or sediment limit for
        # kerosene — both are checked by visual "clear and bright" only, and
        # there's no conductivity requirement either (unlike Jet A-1's
        # mandatory static-dissipator range). All three recorded only.
        "WATER-D6304": (None, None),
        "COND-D2624": (None, None),
        "SED-D473": (None, None),
    },
    # ISO 8217:2017 Table 2, grade ISO-F-RMG 380 (residual/heavy fuel oil).
    # Sulfur uses the IMO 2020 global sulphur cap (0.50% m/m outside an
    # Emission Control Area) since ISO 8217 itself defers to "statutory
    # requirements" rather than setting its own number.
    "MARINE-HFO": {
        "VISC-D445-50": (None, 380.0),
        "DENS-D4052": (None, 1010.0),
        "WATER-D95": (None, 0.50),
        "FLASH-D93": (60.0, None),
        "SULF-D5453": (None, 5000.0),
        # Residual fuel's low-temperature workability is graded by Pour
        # Point (waxy solidification), not "freezing point" (a distinct
        # aviation-fuel crystallization test — see Jet A-1). ISO 8217:2017
        # RMG 380 pour point (ISO 3016; D97 is the ASTM-equivalent method):
        # summer-quality max 0°C (used here), winter-quality is stricter at
        # max -6°C.
        "POUR-D97": (None, 0.0),
        # No universal conductivity spec for residual fuel (it's a
        # combustion fuel, not subject to Jet A-1's aircraft static-safety
        # requirement). Recorded only.
        "COND-D2624": (None, None),
        # ISO 8217 grades "Total Sediment" via its own existent/potential
        # test (not modeled here); D473 (literally titled "Sediment in
        # Crude Oils and Fuel Oils by Extraction") is a legitimate
        # supplementary extraction-method check on residual fuel, recorded
        # for traceability.
        "SED-D473": (None, None),
    },
    # ISO 8217:2017 Table 1, grade ISO-F-DMA (marine gas oil). Sulfur uses
    # the stricter Emission Control Area limit (0.10% m/m) since that's the
    # grade most commonly supplied/traded today regardless of routing.
    "MGO": {
        "DENS-D4052": (None, 890.0),
        "VISC-D445": (2.0, 6.0),
        "FLASH-D93": (60.0, None),
        "CETANE-D613": (40.0, None),
        "SULF-D5453": (None, 1000.0),
        # No confirmed international water-content cap on file for DMA —
        # recorded, not auto pass/fail.
        "WATER-D6304": (None, None),
        # No universal conductivity spec for DMA. Recorded only.
        "COND-D2624": (None, None),
        # ISO 8217's closest real DMA parameter is Micro Carbon Residue
        # (not modeled here), not a D473-style sediment number — typical
        # trace figure, similar to distillate road diesel, informational.
        "SED-D473": (None, 0.01),
    },
    # EN 589:2024 automotive LPG. No density limit is set by the standard
    # (it's a composition-driven spec) — recorded for traceability only.
    "LPG": {
        "VAPOR-D1267": (None, 1550.0),
        "SULF-D5453": (None, 30.0),
        # EN 589 doesn't fix a density number (it's composition-driven, a
        # consequence of the propane/butane ratio rather than an
        # independently graded property) — typical commercial autogas
        # blend range (propane ~500-510 kg/m³ to butane ~570-580 kg/m³),
        # informational.
        "DENS-D4052": (500.0, 580.0),
        # LPG's water content is really checked by a visual "free water"
        # test (ASTM D2713), not Karl Fischer ppm — recorded only.
        "WATER-D6304": (None, None),
    },
    # ASTM D910 / DEF STAN 91-90 leaded aviation gasoline, grade 100LL.
    "AVGAS100LL": {
        "FREEZE-D2386": (None, -58.0),
        "SULF-D5453": (None, 500.0),
        "MON-D2700": (99.6, None),
        "RVP-D5191": (38.0, 49.0),
        "HEAT-D3338": (43.5, None),
        "TEL-D3341": (None, 0.56),
        # D910 doesn't fix a strict density band (it's reported on the
        # certificate, not pass/fail) — typical range for an
        # alkylate/isooctane-based avgas blend, informational.
        "DENS-D4052": (690.0, 710.0),
        # Avgas's flash point is a fixed physical property of such a
        # volatile, gasoline-like fuel — D910 doesn't grade it as a
        # pass/fail spec (RVP governs volatility instead), same reasoning
        # as motor gasoline. Typical range, informational only.
        "FLASH-D56": (-45.0, -35.0),
        # D910 relies on a visual "clear and bright" + free-water check,
        # not a numeric KF ppm limit. Recorded only.
        "WATER-D6304": (None, None),
        # Unlike Jet A-1, D910 doesn't mandate a static-dissipator
        # conductivity range for avgas. Recorded only.
        "COND-D2624": (None, None),
    },
    # Crude oil: every value below is recorded for the assay report, not
    # graded pass/fail — there's no single international acceptance number
    # for e.g. API gravity or sulfur the way there is for a finished fuel;
    # different crude streams simply have different (equally "correct")
    # values. See the FuelType description above for the full reasoning.
    "CRUDE": {
        "API-D287": (None, None),
        "DENS-D4052": (None, None),
        "SULF-D4294": (None, None),
        "BSW-D4007": (None, None),
        "SALT-D3230": (None, None),
        "VAPOR-D6377": (None, None),
        "POUR-D97": (None, None),
        "VISC-D445": (None, None),
        "TAN-D664": (None, None),
        "H2S-D7621": (None, None),
        "FLASH-D93": (None, None),
        # Crude's real distillation test is a multi-cut True Boiling Point
        # assay (run under vacuum for the heavier cuts), not a single D86
        # atmospheric run — reported as a full curve in a real assay;
        # recorded here as a representative point for the assay report.
        # (No separate Karl Fischer/water line: crude's water content is
        # measured together with sediment via BS&W above, its actual
        # governing method, not KF titration. No conductivity line either
        # — that's not a standard crude assay parameter.)
        "DIST-D2892": (None, None),
    },
}

INSTRUMENTS = [
    ("Gas Chromatograph GC-2010", "Gas Chromatograph", "GC2010-004", -5),
    ("Densitometer DMA 4500", "Densitometer", "DMA4500-011", 40),
    ("Pensky-Martens Flash Point Tester", "Flash Point Tester", "PM-93-002", 20),
    ("Karl Fischer Titrator", "Titrator", "KF-6304-007", 90),
    ("Automatic Distillation Unit", "Distillation Unit", "AD-86-003", 150),
    ("Viscometer Bath", "Viscometer", "VB-445-009", 60),
    ("Hydrometer Set (D1298)", "Hydrometer", "HYD-1298-005", 75),
    ("Freeze Point Apparatus", "Freeze Point Tester", "FP-2386-006", 45),
    ("Conductivity Meter", "Conductivity Meter", "COND-2624-008", 100),
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

        # "accounts" grants add/change/delete/view on Client and
        # ClientProfile — Lab Manager/QA need change_clientprofile in
        # particular to approve pending client-portal signups.
        all_apps = ["catalog", "samples", "labtests", "reports", "accounts"]
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
