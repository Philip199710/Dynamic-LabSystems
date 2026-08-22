# Dynamic LabSystems

A lightweight, custom-built LIMS (Laboratory Information Management System) for a fuel/petroleum
testing lab: sample intake and chain of custody, test assignment, results entry with automatic
pass/fail against spec limits, QC trend/control charts, a lab activity dashboard, and
Certificate of Analysis (COA) PDF generation.

This is a **Phase 1 build**: it covers the core day-to-day workflow for a small internal-QC lab
(sample → test → result → report) with room to grow — instrument data feeds, stricter audit
controls, multi-site support, etc. can be added later without a rewrite.

## What's included

- **Sample intake & chain of custody** — register samples with an auto-generated ID
  (`FS-2026-0001`), track status (Received → In Testing → Complete → Disposed), and an automatic
  custody log of every action taken on a sample.
- **Test catalog** — a library of test methods tied to real standards (ASTM D93, D4052, D5453,
  D86, D5191, D6304, D445, D613, D2699, D2500, D56) with per-fuel-type spec limits (min/max).
  Seeded with six fuel types (Gasoline RON95/RON91, Diesel, Jet A-1, Biodiesel, Kerosene) and
  illustrative spec ranges — **review and replace these with your lab's actual validated methods
  and limits before relying on them.**
- **Test assignment & worklists** — assign tests + analyst + due date to a sample; each analyst
  sees their own open worklist.
- **Results entry** — manual entry, automatically flagged PASS / OUT OF SPEC against the spec
  limit for that test + fuel type.
- **Dashboard** — samples by status, open/overdue tests, analyst workload, QC pass/fail rate,
  average turnaround time, instruments overdue for calibration, recent activity feed.
- **Data analysis** — trend/control chart per test method (mean, ±2σ, ±3σ bands) across all
  results on file, built with Chart.js (vendored locally — no external CDN needed).
- **Reporting** — downloadable Certificate of Analysis (COA) PDF per completed sample.
- **Roles** — four groups (Lab Manager, QA, Analyst, Viewer) with sensible default permissions,
  built on Django's standard auth/admin.
- **Instrument registry** — simple equipment list with calibration due dates.

Branding: the "Dynamic LabSystems" logo is wired into the nav bar, the login page, and the COA
PDF header (`static/img/logo.png`) — replace that file with an updated logo any time; no code
changes needed.

## Quick start (local, SQLite — for trying it out)

Requires Python 3.11+.

```bash
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

python manage.py migrate
python manage.py seed_demo        # optional: loads demo fuel types/tests/samples + demo users
python manage.py runserver
```

Visit `http://127.0.0.1:8000/`. If you ran `seed_demo`, log in with any of:

| Username     | Password           | Role        |
|--------------|--------------------|-------------|
| `admin`      | `DynamicLab2026!`  | Superuser / Lab Manager |
| `labmanager` | `DynamicLab2026!`  | Lab Manager |
| `qa1`        | `DynamicLab2026!`  | QA          |
| `analyst1`   | `DynamicLab2026!`  | Analyst     |
| `analyst2`   | `DynamicLab2026!`  | Analyst     |
| `viewer1`    | `DynamicLab2026!`  | Viewer (read-only) |

**Change these passwords (or delete the demo users) before this ever holds real lab data.**

To start from a clean slate instead of the demo data, skip `seed_demo` and create your own
superuser: `python manage.py createsuperuser`. You can then build out your fuel types, test
catalog, and spec limits from `/admin/`.

Run the test suite with `python manage.py test`.

## Deployment

The app is container-first so it can run either in the cloud or entirely inside your own
network — same image either way.

**Recommended to start: cloud-hosted.** Deploy the Docker image to a small managed host (Render,
Railway, Fly.io, or a basic VPS). No on-site IT burden, accessible from anywhere, easy backups.
Good default since there's no data-residency requirement to keep data on-site.

**Alternative: on-premise.** Run the same Docker image on a server or NAS on the lab's own
network if you decide later that data shouldn't leave the building. Nothing else changes.

### Running with Docker

```bash
cp .env.example .env
# edit .env: set a real DJANGO_SECRET_KEY, POSTGRES_PASSWORD, and DJANGO_ALLOWED_HOSTS

docker compose up -d --build
```

This starts Postgres and the app (served by gunicorn, static files served by whitenoise — no
separate web server needed for a small lab's traffic). On first boot, set `SEED_DEMO_DATA=1` in
`.env` to load the demo catalog and users, then set it back to `0` and restart
(`docker compose up -d`) so it doesn't reseed. Put a reverse proxy (Caddy, nginx, or your
platform's built-in one) in front for HTTPS in production.

Back up the `dynamiclab_pgdata` Docker volume regularly — that's where all lab data lives.

### Environment variables

| Variable | Purpose | Default |
|---|---|---|
| `DJANGO_SECRET_KEY` | Django cryptographic signing key — set a real random value in production | dev-only insecure default |
| `DJANGO_DEBUG` | `1` for local dev (verbose errors), `0` in production | `1` |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated hostnames the app will answer for | `*` |
| `DJANGO_TIME_ZONE` | Timezone for displayed timestamps | `Asia/Bangkok` |
| `DATABASE_URL` | `postgres://user:pass@host:5432/dbname` — omit to use local SQLite | SQLite file |
| `SEED_DEMO_DATA` | If `1`, loads demo data on container start (Docker entrypoint only) | `0` |

## Project layout

```
dynamiclab/       Django project settings/urls
accounts/         (role groups live in Django's built-in auth; no custom models yet)
catalog/          FuelType, TestMethod, SpecLimit, Instrument + seed_demo management command
samples/          Sample, ChainOfCustodyEntry
labtests/         SampleTest, TestResult (pass/fail evaluation, status cascading)
dashboard/        Activity dashboard, trend/control chart analytics
reports/          Certificate of Analysis PDF generation
templates/, static/   Shared templates, CSS, logo, vendored Chart.js
```

## Extending it later

- **Instrument data feeds**: results are entered through `labtests.views.enter_result` / the
  `TestResult.record()` model method — a REST endpoint or file-watcher that calls the same
  method is a natural place to wire up direct instrument output.
- **Stricter audit trail / ISO 17025**: `ChainOfCustodyEntry` already logs every material action;
  tightening this into a full audit trail (immutable records, e-signatures, document control)
  is additive, not a redesign.
- **Multi-site**: add a `Site` model and a `site` FK to `Sample`; scope dashboards/worklists by
  site.
