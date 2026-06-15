# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Quick start

```bash
# SQLite (no Docker needed for local dev)
export DATABASE_ENGINE=django.db.backends.sqlite3
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_pacific_ports
python manage.py create_sample_routes
python manage.py create_admin          # admin / admin123
python manage.py runserver             # http://127.0.0.1:8000
```

```bash
# Docker (PostgreSQL + Redis, mirrors production)
docker-compose up --build
docker-compose exec web python manage.py migrate
docker-compose exec web python manage.py seed_pacific_ports
docker-compose exec web python manage.py create_admin
```

## All management commands

```bash
# Core data seeds
python manage.py create_sample_routes    # seed RouteParameters (TCE calculator)
python manage.py create_sample_voyages   # seed FreightVoyage / vessel data
python manage.py create_admin            # create default superuser (admin/admin123)
python manage.py upload_indices          # bulk-upload Baltic index Excel

# Supply forecast (supply app)
python manage.py seed_pacific_ports      # seed ~33 Pacific load/discharge ports
python manage.py ingest_ais              # live AIS websocket (needs AISSTREAM_API_KEY)
python manage.py ingest_ais --replay f.jsonl        # offline replay, no key needed
python manage.py ingest_ais --duration-seconds 120  # run for N seconds then exit
python manage.py ingest_ais --with-aggregation      # also runs aggregate_supply at midnight
python manage.py make_ais_fixture --out f.jsonl     # generate synthetic AIS JSONL for tests/demos
python manage.py aggregate_supply                   # build today's snapshot + signal rows
python manage.py aggregate_supply --date 2025-01-15 # backfill a specific date
```

## Tests

```bash
pytest                           # run all tests
pytest supply/tests.py -v        # supply app tests (27 test cases)
pytest voyage/tests.py -v        # voyage app tests
pytest --cov=supply --cov-report=term-missing
```

## Code quality

```bash
black .
flake8 .
isort .
```

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `DATABASE_ENGINE` | dev only | Set to `django.db.backends.sqlite3` for local SQLite |
| `DATABASE_URL` | prod | PostgreSQL connection string (Render sets automatically) |
| `SECRET_KEY` | always | Django secret key (Render auto-generates) |
| `DEBUG` | always | `False` in production |
| `AISSTREAM_API_KEY` | supply app | Free key from aisstream.io |
| `ALLOWED_HOSTS` | prod | Comma-separated hostnames |
| `CSRF_TRUSTED_ORIGINS` | prod | Comma-separated origins with scheme |
| `TZ` | always | `Asia/Singapore` |

Database config priority (settings.py):
1. `DATABASE_ENGINE=django.db.backends.sqlite3` → SQLite
2. `DATABASE_URL` → dj-database-url parse (Render)
3. `PGDATABASE/PGUSER/PGPASSWORD/PGHOST/PGPORT` → individual Render vars
4. `DATABASE_NAME/USER/PASSWORD/HOST/PORT` → Docker compose vars

## Architecture

FreightDash is a Django 4.2 shipping-analytics web app deployed on Render (Singapore region). Three Django apps: `core`, `voyage`, `supply`.

### `core` app

- **`MenuItem`** — database-driven nav menu managed via Django admin → "Menu Builder". Falls back to `DEFAULT_MENU_ITEMS` in `core/context_processors.py` when the table is empty.
- `context_processors.menu_items` is registered globally and injects `menu_items` into every template.
- To add a new top-level page: append an entry to `DEFAULT_MENU_ITEMS` in `core/context_processors.py` AND add a `MenuItem` row via admin (if the DB table already has rows, the fallback is not used).

### `voyage` app

Root URLconf; all routes mount at `/`.

**Models (`voyage/models.py`):**
- `RouteParameters` — simple TCE calculator routes (distances, speeds, port costs).
- `AvailableIndex` — Baltic/bunker index names, grouped by `vessel_size` (capesize/panamax/supramax/handysize/bunker). Seeded by migration `0003`.
- `DailyIndexValue` — daily index time series, FK to `AvailableIndex`.
- `CustomIndexPreset` — saved cross-vessel index selections.
- `VesselProfile` / `VesselSpeedProfile` / `VesselFuelProfile` / `VesselFuelConsumption` — vessel technical specs with multiple speed/consumption profiles.
- `FreightVoyage` — voyage row in the freight matrix (linked vessel + fuel split basket).
- `VoyageFuelSplit` — weighted fuel basket per voyage (e.g. 70% VLSFO + 30% MGO).
- `FFACurve` / `FFACurvePeriod` — FFA forward curve snapshots (vessel_class title-cased: Capesize/Panamax/Supramax/Handysize).

**Views / pages:**
| URL | View | Purpose |
|---|---|---|
| `/` | `tce_calculator` | Simple TCE ↔ freight-rate calculator |
| `/vessel-compare/` | `vessel_compare` | Multi-vessel TCE comparison |
| `/freight-matrix/` | `freight_matrix` | Date-range matrix: reverse-solve freight from target TCE index |
| `/indices/<vessel>/` | `indices_dashboard` | Daily index table with date filter + CSV |
| `/indices/custom/` | `indices_custom` | Cross-vessel custom index selection with presets |
| `/upload-pdf-indices/` | `upload_pdf_indices` | Upload PDF → extract → verify → save |

**Calculators (`voyage/calculators.py`):**
- `calculate_fuel_and_days` — voyage days, total fuel MT, port expenses.
- `calculate_tce(freight_rate, fuel_price, intake, common_data)` → TCE $/day.
- `calculate_freight_from_tce(target_tce, …)` → freight rate $/MT.
- `calculate_vessel_comparison(global_inputs, voyages, vessels)` → BKI-normalised multi-vessel TCE.

**Admin customisations (`voyage/admin.py`):**
Monkey-patches `admin.site.get_urls`:
- `admin:indices-upload` / `admin:indices-upload-verify` — Excel Baltic index import.
- `admin:indices-config` — reorder/activate/deactivate indices per vessel tab.
- `admin:menu-builder` — link to `core.MenuItem` admin.

### `supply` app

Pacific dry-bulk **vessel supply forecast** from live AIS movements correlated with Baltic index and FFA curve data. One-way dependency: `supply` reads `voyage` models (`DailyIndexValue`, `FFACurve`); nothing in `voyage` depends on `supply`.

**Page:** `/supply-forecast/` — per-class signal cards, dual-axis Chart.js (supply metrics vs TC index), recent port-call table, data-coverage banner.

#### Models (`supply/models.py`)

- **`Port`** — named geofenced load/discharge port. Key fields: `lat`, `lon`, `radius_nm` (default 15, use 20–25 for anchorage-loading ports), `port_type` (load/discharge/both), `basin` (default 'pacific'), `vessel_classes` (JSONField, empty = all).
- **`TrackedVessel`** — one row per MMSI. `vessel_class` = capesize/panamax/supramax/handysize/unknown. `max_draught_m` ratchets up over time.
- **`VesselState`** — OneToOne to TrackedVessel, updated **in place** by the ingester. Current position, laden/ballast, `current_port` FK (null = at sea).
- **`PortCallEvent`** — arrival/departure events (vessel FK, port FK, timestamp, draught, loading condition).
- **`DailySupplySnapshot`** — unique on `(date, vessel_class, basin)`. 5 rows/day (4 classes + 'all'). Fields: in-port counts by type, at-sea counts by condition, expected-open proxies, 24 h arrival/departure deltas, average speeds.
- **`SupplySignal`** — unique on `(date, vessel_class)`. `direction` (bullish/bearish/neutral), `score` (≈ −3..+3), `confidence` (0–1), `method` (regression/zscore/insufficient), `drivers` (JSON list of plain-English strings), `data_days`. Kept for backtesting.

SNAPSHOT_CLASSES = `['capesize', 'panamax', 'supramax', 'handysize']`

#### AIS ingestion pipeline

```
aisstream.io websocket
    │
    ▼
supply/ingest.py  AISIngestor
    │  • In-memory CachedVessel cache (no per-message DB writes)
    │  • Write only when: moved >5 nm, draught delta ≥0.3 m,
    │    geofence crossing, or >30 min elapsed
    │  • Emits PortCallEvent on arrival/departure
    │
    ▼
VesselState (upsert in place)  +  PortCallEvent (append-only)
    │
    ▼
supply/aggregation.py  build_snapshot()
    │  • Runs once/day (midnight SGT)
    │  • Staleness filter: last_seen within 48 h
    │
    ▼
DailySupplySnapshot  +  SupplySignal
```

**`supply/ingest.py` — `AISIngestor`:**
- Subscribes to aisstream.io with two Pacific bounding boxes: `[[-45,90],[15,160]]` (SE Asia/Australia) and `[[15,105],[48,150]]` (China/Japan/Korea).
- Message types: `PositionReport`, `ShipStaticData`.
- `replay(lines)` feeds JSONL through the same `process_message` path — used by tests and keyless demos.
- Reconnect loop with exponential backoff (5 s → 300 s).

**`supply/geo.py`:**
- `haversine_nm(lat1, lon1, lat2, lon2)` — great-circle distance in nautical miles.
- `find_containing_port(lat, lon, ports)` — returns `PortGeo` if inside any port circle.
- `is_departed(lat, lon, port, hysteresis=1.25)` — requires distance > radius × 1.25 to prevent geofence flapping.
- `nearest_port(lat, lon, ports)` — closest port (for expected-open estimate).

**`supply/classification.py`:**
- `is_dry_bulk_candidate(ship_type)` — AIS types 70–79 (tankers 80–89 excluded).
- `classify_vessel(length_m, max_draught_m)` — length bands: cape ≥270 m, panamax 215–270, supramax 185–215, handysize 150–185, <150 m ignored. Draught bands as fallback when length missing; length wins on disagreement.
- `detect_loading_condition(draught_m, max_draught_m, ratio=0.80)` — laden if draught/max ≥ 0.80; unknown if draught missing or max_draught < 8 m.

#### Daily aggregation (`supply/aggregation.py`)

`build_snapshot(target_date, basin='pacific', staleness_hours=48, open_speed_kn=12.0)`:
- Universe: `VesselState` where `last_seen` within 48 h, `is_excluded=False`.
- In-port split by port_type; at-sea split by loading_condition.
- `expected_open_7d/14d` = vessels in discharge ports + laden vessels whose haversine / (12 kn × 24) ≤ 7/14 days.
- After snapshots, calls `analytics.generate_signal` and persists `SupplySignal` for each class.

`week_over_week(recent_snapshots, field)` — delta vs 7 days ago, used in UI cards.

#### Signal model (`supply/analytics.py`)

```
CLASS_INDEX_MAP = {
    'capesize':  'BCI 5TC',
    'panamax':   'BPI 82TC',
    'supramax':  'BSI 58TC',
    'handysize': 'BHSI 38TC',
}

FFA_CLASS_MAP = {   # matches FFACurve.vessel_class (title-cased)
    'capesize': 'Capesize', 'panamax': 'Panamax',
    'supramax': 'Supramax', 'handysize': 'Handysize',
}
```

**Metric sign convention** (METRIC_SIGN dict):
- Bearish (−1): `ballast_at_sea_count`, `expected_open_7d`, `in_port_discharge_count` → rising = more supply coming.
- Bullish (+1): `laden_at_sea_count`, `in_port_load_count` → rising = tonnage absorbed.

**Signal generation (`generate_signal`):**

| History | Method | Confidence cap |
|---|---|---|
| < 14 data days | `insufficient` | ≤ 0.10 |
| < 8 complete weeks | `zscore` heuristic | ≤ 0.60 |
| ≥ 8 weeks | `regression` (blended 0.6·lstsq + 0.4·zscore) | ≤ 0.90 |

Z-scores computed over 28-day and 84-day rolling windows (`min_periods = max(7, window//3)`). Lagged correlations are Pearson on weekly (W-FRI) resampled changes, lags 1–4 weeks. FFA contango/backwardation (slope vs spot > +2 % / < −2 %) appended as a driver and ±0.05 confidence modifier.

Drivers are plain-English strings, e.g.:
> "Ballast count 23 % above 12-week avg (z = +1.4) → bearish pressure"

#### Supply forecast page

**`supply/views.py`:**
- `supply_forecast(request)` — builds 4 signal cards, fetches last 30 port-call events, assembles the data-coverage banner (first snapshot date, days of history, vessels seen <48 h, last ingest heartbeat).
- `supply_chart_data(request, vessel_class)` — JSON: 180 days of supply series + TC index for Chart.js dual-axis.

**URLs (`supply/urls.py`):**
- `/supply-forecast/` — main page.
- `/supply-forecast/chart-data/<slug:vessel_class>/` — JSON endpoint.

Mounted via `path('', include('supply.urls'))` in `config/urls.py` (before `voyage.urls`).

#### Seeded ports (`seed_pacific_ports`)

~33 Pacific dry-bulk load and discharge ports including:
- **Australia (load):** Port Hedland, Dampier, Port Walcott (iron ore); Newcastle, Hay Point, Gladstone, Abbot Point, Port Kembla (coal).
- **Indonesia (load, r=25):** Samarinda, Taboneo, Balikpapan, Tarahan, Muara Berau.
- **China (discharge):** Qingdao, Caofeidian, Jingtang, Rizhao, Ningbo-Zhoushan, Bayuquan, Fangcheng, Zhanjiang, Lianyungang, Nansha.
- **Japan:** Kashima, Oita, Mizushima, Kisarazu.
- **Korea:** Gwangyang, Pohang, Dangjin.
- **Taiwan:** Kaohsiung, Taichung.
- **Singapore:** anchorage waypoint (port_type='both').

#### Tests (`supply/tests.py`)

27 test cases, pytest-django / Django `TestCase` style:
- `ClassificationTestCase` — vessel class bands, missing dims, length/draught disagreement.
- `LoadingConditionTestCase` — ratio=0.80 boundary, missing draught, low max_draught.
- `GeofenceTestCase` — haversine sanity, containment at radius edge, hysteresis.
- `IngestReplayTestCase` — JSONL track crossing a port fence: vessel created, one arrival + one departure, write-throttle collapses near-identical positions.
- `AggregationTestCase` — synthetic VesselState rows → counts, expected_open logic, stale exclusion, idempotent re-run.
- `AnalyticsTestCase` — 16 weeks of synthetic data → lagged correlations, regression bearish signal; truncated → zscore; 5 days → insufficient. FFA backwardation stance.
- `SupplyForecastViewTestCase` — HTTP 200 from `/supply-forecast/` and `/supply-forecast/chart-data/capesize/`.

## Deployment

Production is Render (Singapore region). See `render.yaml` and `RENDER_DEPLOYMENT.md`.

### Services in render.yaml

| Service | Type | Purpose |
|---|---|---|
| `freightdash-web` | web | Django/gunicorn + WhiteNoise static files |
| `freightdash-ais-poll` | cron `*/20 * * * *` | AIS ingest for 18 min of every 20 (--duration-seconds 1080) |
| `freightdash-supply-agg` | cron `15 16 * * *` | Daily snapshot + signal (00:15 SGT = 16:15 UTC) |
| `freightdash` | database | PostgreSQL 15 |

> `AISSTREAM_API_KEY` is marked `sync: false` (set it manually in Render dashboard). One concurrent connection per free key — do not run the docker-compose `ais_ingester` and the Render cron on the same key simultaneously.

### Static files

WhiteNoise `CompressedStaticFilesStorage` — no manifest JSON, avoids startup failures on ephemeral containers. `collectstatic` runs inside `entrypoint.sh` at container startup.

### First-time setup on Render

```bash
# In Render Dashboard → Service → Shell
python manage.py migrate
python manage.py seed_pacific_ports
python manage.py create_admin
```

## Key file map

```
config/
  settings.py          Django settings (DB config, INSTALLED_APPS, AISSTREAM_API_KEY)
  urls.py              Root URLconf: supply.urls then voyage.urls

core/
  context_processors.py  DEFAULT_MENU_ITEMS (fallback nav when MenuItem table empty)
  models.py              MenuItem

voyage/
  models.py            RouteParameters, AvailableIndex, DailyIndexValue, FFACurve, …
  views.py             All voyage page views + chart JSON endpoints
  calculators.py       TCE / freight-rate / vessel-comparison logic
  admin.py             Monkey-patched admin (index upload, config, menu builder)
  urls.py              Voyage URL patterns
  ffa_utils.py         FFA curve parsing helpers
  migrations/0003_…    Seeds AvailableIndex rows (BCI 5TC, BPI 82TC, …)

supply/
  models.py            Port, TrackedVessel, VesselState, PortCallEvent,
                       DailySupplySnapshot, SupplySignal
  geo.py               haversine_nm, find_containing_port, is_departed, nearest_port
  classification.py    is_dry_bulk_candidate, classify_vessel, detect_loading_condition
  ingest.py            AISIngestor (websocket worker + replay)
  aggregation.py       build_snapshot, week_over_week
  analytics.py         generate_signal, SignalResult, CLASS_INDEX_MAP, FFA_CLASS_MAP
  views.py             supply_forecast, supply_chart_data
  urls.py              /supply-forecast/ routes
  admin.py             6 ModelAdmin registrations
  tests.py             27 test cases
  templates/supply/supply_forecast.html
  management/commands/
    seed_pacific_ports.py
    ingest_ais.py
    make_ais_fixture.py
    aggregate_supply.py

templates/
  base.html            Global base template
  admin/               Custom admin templates (index upload/config)

Dockerfile
docker-compose.yml     db + web + ais_ingester + redis
render.yaml            Render deployment config (web + 2 crons + DB)
requirements.txt       Python deps (websockets==12.0 added for AIS)
```

## Caveats and known limitations

- **Terrestrial AIS only:** aisstream.io has sparse mid-ocean coverage. In-port counts and port-call events are the most reliable metrics; at-sea counts are documented as undercounts in the UI.
- **Cold start:** signal reads `insufficient` for ~2 weeks, `zscore`-only until ~8–10 weeks, `regression` after. Coverage banner makes this explicit on the page.
- **Draught quality:** crew-entered, often stale. `max_draught_m` ratchets up, so early laden/ballast splits may be noisy.
- **Cron gaps:** AIS cron polls 18 of every 20 minutes. Geofence transitions that happen in the 2-minute gap are detected on the next position message, so port calls are delayed rather than lost; however, rapid in/out flicker during that gap may be missed.
- **SQLite concurrency:** if running both `ingest_ais --replay` and `runserver` against the same SQLite file, occasional `database is locked` errors are possible. Use docker-compose Postgres for concurrent processes.
