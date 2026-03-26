# TCE Calculator - FreightDash

## Overview

The TCE (Time Charter Equivalent) Calculator is a Django-based web application that converts a legacy PHP script for calculating freight rates and voyage economics for Capesize bulk carriers. The calculator is now the homepage of FreightDash and provides an intuitive interface for shipping professionals to perform complex voyage cost calculations.

## Features

### Core Functionality

1. **TCE Calculation**: Calculate Time Charter Equivalent from a given freight rate
   - Formula: TCE = (Freight Revenue - Port Expenses - Fuel Cost) / Voyage Days
   - Accounts for fuel consumption, port expenses, and voyage duration

2. **Reverse Freight Calculation**: Calculate the freight rate needed to achieve a target TCE
   - Formula: Freight Rate = [TCE × Days + Port Expenses + (Fuel × Price)] / [Intake × (1 - Commission)]

3. **Route Management**: Pre-configured shipping routes with customizable parameters
   - China-Australia
   - Brazil-China
   - South Africa-India
   - Indonesia-Pacific
   - West Africa-China

4. **Parameter Flexibility**: All voyage parameters can be adjusted for accurate calculations
   - Distance parameters (ballast and laden)
   - Cargo parameters (intake, load/discharge rates)
   - Port expenses at load and discharge ports
   - Commission and sea margin percentages
   - Ship speed and fuel consumption rates

## Architecture

### Django App Structure

```
voyage/
├── migrations/          # Database migrations
├── management/
│   └── commands/
│       └── create_sample_routes.py    # Management command for sample data
├── templates/
│   └── voyage/
│       └── tce_calculator.html        # Main calculator interface
├── admin.py            # Jazzmin admin configuration
├── apps.py             # App configuration
├── calculators.py      # Core calculation logic
├── forms.py            # Django forms for input validation
├── models.py           # RouteParameters database model
├── tests.py            # Unit tests
├── urls.py             # URL routing
└── views.py            # View logic for TCE calculator
```

### Database Model: RouteParameters

```python
class RouteParameters(models.Model):
    route                    # Route name (unique)
    ballast_distance         # Nautical miles
    laden_distance           # Nautical miles
    intake                   # Metric tons (cargo quantity)
    load_rate                # MT per day
    discharge_rate           # MT per day
    turntime_hours           # Hours in port
    port_exp_load_port       # Currency units
    port_exp_discharge_port  # Currency units
    freight_commission_pct   # Percentage
    sea_margin_pct           # Percentage (for speed variance)
    ballast_speed            # Nautical miles per hour
    laden_speed              # Nautical miles per hour
    ballast_consumption      # MT per 24 hours
    laden_consumption        # MT per 24 hours
    port_consumption         # MT per 24 hours
```

## Core Calculation Functions

### calculate_fuel_and_days()
Calculates fuel consumption, voyage days, and port expenses based on voyage parameters.

**Inputs:**
- Voyage distance parameters (ballast & laden)
- Ship speed and consumption rates
- Cargo and port parameters
- Sea margin percentage

**Outputs:**
- `voyage_days`: Total voyage duration including loading/discharging
- `total_fuel_consumed`: Total fuel consumption (in MT) including sea margin
- `total_port_expenses`: Combined port expenses
- `freight_commission`: Decimal representation of commission percentage

**Key Formula:**
```
Fuel Ballast = (Distance / Speed / 24) × Consumption × (1 + Sea Margin)
Fuel Laden = (Distance / Speed / 24) × Consumption × (1 + Sea Margin)
Fuel Loading = ((Intake / Load Rate) + Turntime) × Port Consumption
Fuel Discharge = (Intake / Discharge Rate) × Port Consumption
```

### calculate_tce()
Calculates TCE from a known freight rate.

**Inputs:**
- Freight rate (currency/MT)
- Fuel price (currency/MT of fuel)
- Cargo intake (MT)
- Common data from calculate_fuel_and_days()

**Output:**
- TCE in currency per day

**Formula:**
```
Freight Revenue = Freight Rate × Intake × (1 - Commission)
TCE = (Freight Revenue - Port Expenses - Fuel Cost) / Voyage Days
```

### calculate_freight_from_tce()
Calculates the freight rate needed to achieve a target TCE.

**Inputs:**
- Target TCE (currency/day)
- Fuel price (currency/MT of fuel)
- Cargo intake (MT)
- Common data from calculate_fuel_and_days()

**Output:**
- Required freight rate in currency per MT

**Formula:**
```
Freight Rate = [TCE × Days + Port Expenses + (Fuel × Price)] / [Intake × (1 - Commission)]
```

## User Interface

### Layout
- **Professional Bootstrap 5 styling** for modern, responsive design
- **Collapsible parameters section** for cleaner interface
- **Real-time route selection** to auto-populate default parameters
- **Separate pricing inputs section** for fund-related data
- **Live results display** showing calculated TCE or freight rate

### Navigation
- Logo and app name in navbar with ship icon
- Quick links to TCE Calculator (home) and Admin Panel
- Responsive mobile menu

## API Routes

| Route | Method | Purpose |
|-------|--------|---------|
| `/` | GET/POST | TCE Calculator form and calculations |
| `/admin/` | GET | Jazzmin admin interface |
| `/admin/voyage/routeparameters/` | GET/POST | Manage routes in admin |

## Installation & Setup

### 1. Initialize the App
```bash
python manage.py makemigrations voyage
python manage.py migrate voyage
```

### 2. Create Sample Routes
```bash
python manage.py create_sample_routes
```

This creates 5 pre-configured shipping routes:
- China-Australia
- Brazil-China
- South Africa-India
- Indonesia-Pacific
- West Africa-China

### 3. Access the Application
```
http://localhost:8000/
```

## Data Flow

```
User Input (Form)
       ↓
TCECalculatorForm validation
       ↓
Extract cleaned data
       ↓
calculate_fuel_and_days()
       ↓
User selects calculation type
       ├─→ Calculate TCE
       │   calculate_tce() ← Returns TCE value
       │
       └─→ Calculate Freight
            calculate_freight_from_tce() ← Returns Freight Rate
       ↓
Render results on template
```

## Testing

Run unit tests with:
```bash
python manage.py test voyage
```

Tests include:
- Route creation in database
- Fuel and days calculation accuracy
- Form validation

## Customization

### Adding New Routes
Use Django admin at `/admin/voyage/routeparameters/`:
1. Click "Add Route Parameter"
2. Enter route name and all parameters
3. Save

Or use management command:
```bash
python manage.py create_sample_routes
```

### Modifying Calculations
Edit `voyage/calculators.py` to change calculation logic. All functions are:
- Fully documented
- Port from original PHP code
- Independently testable

### Styling
- Edit `voyage/templates/voyage/tce_calculator.html` for form styling
- Modify `/templates/base.html` for site-wide styles
- Uses Bootstrap 5 and custom CSS variables

## Integration with Jazzmin Admin

The TCE Calculator is fully integrated with Jazzmin (AdminLTE):
- **Admin interface** at `/admin/voyage/routeparameters/`
- **Organized fieldsets** grouping related parameters
- **Search functionality** to find routes by name
- **List view** showing key metrics (route, intake, distances)

## Performance Considerations

1. **Database queries**: Route parameters are stored in DB, not hardcoded
2. **Caching**: Calculations are in-memory (no DB writes during calculation)
3. **Form rendering**: All forms use Django's form system for efficient rendering
4. **Sea margin**: Applied as a percentage multiplier on distance-based consumption

## Data Validation

The TCECalculatorForm validates:
- All numeric fields accept decimal values
- Route selection is optional (defaults can be used)
- Form submission only processes valid data

## Browser Compatibility

- Modern browsers (Chrome, Firefox, Safari, Edge)
- Responsive design for desktop and tablet
- Mobile-friendly interface

## Future Enhancements

Potential additions:
- Export calculations to PDF
- Historical calculation storage
- User accounts and saved calculations
- Advanced reporting and analytics
- API endpoints for programmatic access
- Calculate profitability with operating costs
- Support for additional vessel types (Panamax, Handy, Supramax)

## Troubleshooting

### Page not loading
1. Ensure Docker containers are running: `docker compose up -d`
2. Check migrations: `python manage.py migrate voyage`
3. Verify settings.py includes 'voyage' in INSTALLED_APPS

### Form not submitting
1. Clear browser cache (hard refresh)
2. Check console for JavaScript errors
3. Verify CSRF token is included in form

### Sample routes not appearing
1. Run: `python manage.py create_sample_routes`
2. Check database connection
3. Verify RouteParameters table exists: `python manage.py migrate voyage`

### Admin changes not showing
1. Clear browser cache
2. Restart Django server
3. Check user has admin permissions

## Files Modified

- `config/settings.py` - Added 'voyage' to INSTALLED_APPS, added templates directory
- `config/urls.py` - Added voyage URL patterns, set as homepage

## Files Created

- `voyage/` - New Django app with complete TCE calculator implementation
- `templates/base.html` - Base template for all pages
- `voyage/templates/voyage/tce_calculator.html` - Main calculator template

---

**Last Updated:** March 26, 2024  
**Version:** 1.0  
**Status:** Production Ready
