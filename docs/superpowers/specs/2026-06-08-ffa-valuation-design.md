# FFA Valuation Module — Design Spec
_Date: 2026-06-08_

## Context

Users receive FFA (Forward Freight Agreement) curves from brokers as plain text (bid/offer prices per period). They want to paste that curve into FreightDash, set a delivery date and employment period, and instantly see what blended FFA rate applies — and what that means for specific vessels given their % efficiency vs BKI standard. Today there is no tool for this; it's done manually with a calculator.

## Overview

A new page `/ffa-valuation/` in the `voyage` app. The user pastes a raw FFA curve, it is parsed and shown as an editable table, then saved to the database. Given a delivery date and period length (in months), the tool resolves which FFA periods apply, weights them by calendar days, and shows the blended offer-side rate. Vessels from the vessel-compare tool can be added to see their adjusted rates. All results update via debounced AJAX when the delivery date or period slider changes.

---

## Data Model

Two new models in `voyage/models.py`:

### `FFACurve`
| Field | Type | Notes |
|---|---|---|
| `vessel_class` | CharField(50) | Parsed from first line of curve, e.g. "Panamax" |
| `raw_text` | TextField | Original pasted text, preserved for re-editing |
| `created_at` | DateTimeField(auto_now_add=True) | Used to find "most recent" curve on page load |

### `FFACurvePeriod`
| Field | Type | Notes |
|---|---|---|
| `curve` | FK → FFACurve | CASCADE delete |
| `label` | CharField(20) | e.g. "Q3", "Jul", "Cal27", "Balmo" |
| `period_type` | CharField(20) | choices: `balmo`, `monthly`, `quarterly`, `combined`, `calendar_year` |
| `start_date` | DateField | Resolved start of this period |
| `end_date` | DateField | Resolved end of this period (inclusive) |
| `bid` | DecimalField(10,2) | |
| `offer` | DecimalField(10,2) | |

`combined` period types (Q34, Jun+Jul, Jun-Dec) are stored for reference but **excluded from blending** — they are derived prices, not leaf periods.

---

## Parser (`voyage/ffa_utils.py`)

### `parse_ffa_text(text: str, reference_date: date) -> dict`

Returns `{"vessel_class": str, "periods": [{"label", "period_type", "start_date", "end_date", "bid", "offer"}, ...]}`

**Label resolution rules** (all relative to `reference_date`):

| Label pattern | Resolution |
|---|---|
| First non-numeric line | vessel_class (e.g. "Pmax" → "Panamax") |
| `Balmo` | `reference_date` → last day of that month |
| `Jan`–`Dec` (single month name) | That month; if already past in current year, use next year |
| `Q1` / `Q2` / `Q3` / `Q4` | Jan–Mar / Apr–Jun / Jul–Sep / Oct–Dec; year inferred by order in curve |
| `Q34` | Treat as `combined`; start=Q3 start, end=Q4 end |
| `MonA + MonB` (e.g. `Jun + Jul`) | `combined`; start=MonA start, end=MonB end |
| `Mon-Mon` (e.g. `Jun-Dec`) | `combined`; start first month, end last month |
| `CalYY` (e.g. `Cal27`) | Jan 1 – Dec 31 of 20YY |

Line format: `LABEL BID / OFFER` — whitespace and comma-separators tolerated. Lines that don't match are silently skipped (header/empty lines).

---

## Blending Algorithm (`voyage/ffa_utils.py`)

### `resolve_employment_periods(curve_periods, start_date, period_months) -> dict`

Returns:
```python
{
    "end_date": date,
    "blended_offer": Decimal,
    "breakdown": [
        {"label": str, "bid": Decimal, "offer": Decimal, "days": int, "weight": Decimal},
        ...
    ]
}
```

**Steps:**
1. Compute `end_date = start_date + period_months calendar months` (e.g. Jul 15 + 9m = Apr 15)
2. For each calendar month wholly or partially within `[start_date, end_date)`:
   - Find the most granular leaf period covering that month: **monthly > quarterly > calendar_year** (combined periods excluded)
   - Calculate `days` = actual calendar days of that month within the employment window (handles partial first/last month)
3. `blended_offer = sum(offer × days) / sum(days)` across all months
4. Consolidate consecutive months with the same period into one breakdown row (e.g. Oct/Nov/Dec all from Q4 → one "Q4 2026" row)

---

## Views & URLs

### `voyage/urls.py` additions
```python
path('ffa-valuation/', views.ffa_valuation, name='ffa-valuation'),
path('ffa-valuation/calculate/', views.ffa_valuation_calculate, name='ffa-valuation-calculate'),
```

### `ffa_valuation(request)`
- **GET**: Load most recent `FFACurve` (ordered by `-created_at`). Render template with curve data (or empty state).
- **POST `action=parse`**: Accept `raw_text`, call `parse_ffa_text`, return JSON of parsed periods. Does **not** save to DB.
- **POST `action=save`**: Save `FFACurve` + `FFACurvePeriod` rows. Return `{"curve_id": int}`.

### `ffa_valuation_calculate(request)` — AJAX, POST
Input JSON:
```json
{
  "curve_id": 5,
  "delivery_date": "2026-07-15",
  "period_months": 9,
  "vessel_ids": [1, 3]
}
```
Output JSON:
```json
{
  "blended_offer": 18522,
  "end_date": "2027-04-15",
  "coverage_warning": null,
  "timeline": [
    {"label": "Q3 2026", "offer": 20867, "start": "2026-07-01", "end": "2026-09-30", "in_window": true},
    ...
  ],
  "breakdown": [
    {"label": "Q3 2026", "bid": 20666, "offer": 20867, "days": 78, "weight": 0.286},
    ...
  ],
  "vessels": [
    {"name": "Vessel A", "pct": 103.5, "adjusted_rate": 19170},
    ...
  ]
}
```

**Vessel % source**: For each `vessel_id`, re-run `calculate_vessel_comparison` with the current `VesselCompareConfig` settings to obtain the live weighted-average % for that vessel (same number shown on the vessel compare page). `adjusted_rate = blended_offer × vessel_weighted_avg_pct`.

**Missing period coverage**: If any calendar month in the employment window has no leaf period in the curve, the endpoint returns `"coverage_warning": "Curve does not cover <month> <year> — extend the curve or shorten the period"` and `blended_offer: null`. The UI displays the warning prominently and disables the KPI cards.
```

---

## Template: `voyage/templates/voyage/ffa_valuation.html`

Extends `base.html`. Four sections:

### 1. Curve Entry Card
- Textarea (pre-filled with `raw_text` of most recent curve)
- "Parse" button → POST `action=parse` → renders editable `<table>` with bid/offer cells
- "Save Curve" button → POST `action=save` → shows success toast
- Vessel class badge shown once parsed (e.g. "Panamax")

### 2. Controls Bar
- Day-granularity date input (`<input type="date">`) — default today
- Period slider (1–36 months) + numeric display ("9 months")
- Both trigger debounced AJAX to `/ffa-valuation/calculate/` (350ms debounce)

### 3. Timeline + KPI Strip
- Gantt-style bar: FFA periods as blocks with offer price labels; employment window overlaid as a bordered rectangle
- KPI cards: "Blended FFA (100%)" always first, then one card per added vessel
- "Add vessel" button → dropdown of `ComparisonVessel` names → adds a card

### 4. Breakdown Table
| Period | Bid | Offer (used) | Days | Weight | Contribution |
- Footer row: Blended total
- Bid column shown in muted colour; Offer highlighted green

---

## Navigation

Add to `DEFAULT_MENU_ITEMS` in `core/context_processors.py`:
```python
{"label": "FFA Valuation", "url": "/ffa-valuation/", "icon": "fa-chart-line"}
```

---

## Verification

1. Paste the sample Pmax curve → click Parse → verify all 15 periods appear in the editable table with correct bid/offer values
2. Click Save → refresh page → curve auto-loads from DB
3. Set delivery = Jul 1 2026, period = 9 months → breakdown should show Q3/Q4/Q1 with equal 3/9 weights → blended = (20867 + 19550 + 15150) / 3 = **$18,522**
4. Set delivery = Jul 15 2026, period = 9 months → Jul gets 17/273 days, Apr gets 15/273 days; verify blended shifts slightly lower
5. Add a vessel with 103.5% from vessel-compare → adjusted rate card shows **$19,170**
6. Move period slider from 9 → 12 months → timeline and KPIs update within 350ms
7. Edit an offer value in the table (to correct a parser error) → Save → recalculate → new value reflected
