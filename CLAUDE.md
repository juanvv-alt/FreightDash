# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

**Local development (SQLite):**
```bash
# Set DATABASE_ENGINE=django.db.backends.sqlite3 in your environment or .env
python manage.py migrate
python manage.py runserver
```

**Docker (PostgreSQL):**
```bash
docker-compose up --build        # starts db, web (port 8000), and redis
docker-compose exec web python manage.py migrate
docker-compose exec web python manage.py createsuperuser
```

**Tests:**
```bash
pytest                           # run all tests
pytest voyage/tests.py::TCECalculatorTestCase::test_fuel_and_days_calculation  # single test
pytest --cov=voyage --cov-report=term-missing  # with coverage
```

**Code quality:**
```bash
black .
flake8 .
isort .
```

**Management commands:**
```bash
python manage.py create_sample_routes    # seed RouteParameters
python manage.py create_sample_voyages   # seed FreightVoyage / vessel data
python manage.py upload_indices          # bulk-upload Baltic index Excel
python manage.py create_admin            # create default superuser
```

**Database config priority** (settings.py):
1. `DATABASE_ENGINE=django.db.backends.sqlite3` → SQLite (local dev)
2. `DATABASE_URL` env var → dj-database-url parse (Render)
3. Individual `PGDATABASE/PGUSER/PGPASSWORD/PGHOST/PGPORT` vars (Render alternative)
4. Discrete `DATABASE_NAME/USER/PASSWORD/HOST/PORT` vars (Docker compose default)

## Architecture

FreightDash is a Django 4.2 shipping-analytics web app deployed on Render. It has two Django apps:

### `core` app
- **`MenuItem`** — database-driven navigation menu, managed via Django admin's "Menu Builder". Falls back to `DEFAULT_MENU_ITEMS` in `context_processors.py` when the table is empty or unreachable.
- `context_processors.menu_items` is registered globally and injects `menu_items` into every template.

### `voyage` app
This is the main app. All routes are mounted at `/` (the voyage URLconf is the root URLconf).

**Models in `voyage/models.py`:**
- `RouteParameters` — legacy simple TCE calculator routes (ballast/laden distance, speeds, consumption, port costs).
- `AvailableIndex` — configurable list of Baltic/bunker index names, grouped by `vessel_size` (capesize/panamax/supramax/handysize/bunker). Controls what appears in the indices dashboard and upload flows.
- `DailyIndexValue` — time series of daily index values, FK to `AvailableIndex`.
- `CustomIndexPreset` — saved cross-vessel index selections for the custom indices view.
- `VesselProfile` / `VesselSpeedProfile` / `VesselFuelProfile` / `VesselFuelConsumption` — vessel technical particulars with multiple speed and fuel consumption profiles per vessel.
- `FreightVoyage` — voyage assumptions for the freight matrix (linked to a vessel and its profiles, with fuel split baskets).
- `VoyageFuelSplit` — weighted fuel index basket per voyage (e.g., 70% VLSFO + 30% MGO).

**Views / pages:**
| URL | View | Purpose |
|-----|------|---------|
| `/` | `tce_calculator` | Simple TCE ↔ freight-rate calculator using `RouteParameters` |
| `/vessel-compare/` | `vessel_compare` | Multi-vessel TCE comparison (BKI standard breakeven) |
| `/freight-matrix/` | `freight_matrix` | Date-range matrix: freight rate per voyage row, reverse-solved from target TCE index |
| `/indices/<vessel>/` | `indices_dashboard` | Daily index table by vessel class with date-range filter and CSV download |
| `/indices/custom/` | `indices_custom` | Cross-vessel custom index selection with saveable presets |
| `/upload-pdf-indices/` | `upload_pdf_indices` | Upload a PDF of Baltic indices → extract tables → verify → save |

**Calculators (`voyage/calculators.py`):**
- `calculate_fuel_and_days` — common intermediate (voyage days, total fuel MT, port expenses).
- `calculate_tce(freight_rate, fuel_price, intake, common_data)` → TCE $/day.
- `calculate_freight_from_tce(target_tce, …)` → freight rate $/MT (algebraic inverse).
- `calculate_vessel_comparison(global_inputs, voyages, vessels)` → multi-vessel BKI-normalised TCE comparison with duration-weighted averages.

**Freight matrix logic** (inline in `views.py`):
The matrix iterates over `FreightVoyage` objects for a date range, resolves target TCE from `daily_hire_index` values and blended fuel price from `VoyageFuelSplit`, then reverse-solves the freight rate. Missing exact-date values fall back to the most recent available value (tracked via bisect on sorted date lists, marked with an asterisk `*` in the UI).

**Index upload flows (two separate paths):**
1. **Excel** (admin panel → "Upload Baltic Indices"): expects a `Baltic` sheet with `RateDate`, `RatePeriodDescription` (filters `Spot` rows only), and `Value` columns. Requires all indices to already exist in `AvailableIndex`; aborts otherwise. Two-step: extract → verify/map → import.
2. **PDF** (`/upload-pdf-indices/`): uses `pdfplumber` to extract tables from a PDF, parses dates from headers/cells, creates missing `AvailableIndex` entries automatically, two-step: extract → verify → save.

**Admin customisations (`voyage/admin.py`):**
Custom admin views are injected by monkey-patching `admin.site.get_urls`:
- `admin:indices-upload` / `admin:indices-upload-verify` — Excel Baltic index import.
- `admin:indices-config` — reorder/activate/deactivate indices per vessel tab.
- `admin:menu-builder` — link to `core.MenuItem` admin (navigation management).

**Templates:**
- `templates/base.html` — global base.
- `voyage/templates/voyage/*.html` — all voyage app templates.
- `templates/admin/*.html` — custom admin templates for index upload/config.

## Deployment

Production is Render (`freightdash.onrender.com`). See `render.yaml` and `RENDER_DEPLOYMENT.md`. Static files served via WhiteNoise with `CompressedStaticFilesStorage` (no manifest JSON needed, avoids startup failures on ephemeral containers). Timezone is `Asia/Singapore`.
