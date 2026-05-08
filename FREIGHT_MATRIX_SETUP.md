# Freight Matrix Configuration Guide

The Freight Matrix calculates daily freight rates for configured voyages based on:
- Daily hire index values (TCE targets)
- Fuel price indices
- Voyage parameters (distances, speeds, consumption rates)
- Vessel capabilities

## Setup Steps

### 1. Create Vessel Profiles (Admin > Vessel Parameters)
Define vessel characteristics:
- Name, DWT, Draft, Grain Capacity
- Port consumption rates

### 2. Create Speed Profiles (via Vessel)
Define speed variants:
- Ballast Speed (knots)
- Laden Speed (knots)
- Mark as Default if it should be used by default

### 3. Create Fuel Profiles (via Vessel)
Define fuel consumption profiles:
- Add fuel lines (VLSFO, MGO, etc.)
- Sea and port consumption rates per fuel type
- Mark as Default if it should be used by default

### 4. Create Indices (Admin > Available Indices)
Define price and rate indices:
- **Hire Indices** (e.g., C2, BCI, P1A, etc.) - used as daily TCE targets
- **Fuel Indices** (e.g., Singapore IFO 380, MGO, etc.) - used for fuel price blending

Mark indices as active and assign to vessel size.

### 5. Upload Daily Index Values (Admin > Upload Baltic Indices)
Upload Excel files with:
- Date column
- Index columns matching configured indices

Supported date formats: YYYY-MM-DD, DD-MM-YYYY, MM/DD/YYYY, DD/MM/YYYY

**Large files:** Read-only mode is enabled for better performance with big Excel files.
**Missing indices:** Any index columns not yet configured will be auto-created in the system.

### 6. Create Freight Voyages (Admin > Freight Voyages)
Configure voyage economics:
- **Vessel**: Link to vessel profile
- **Speed/Fuel Profiles**: Optional; falls back to defaults
- **Daily Hire Index**: CRITICAL - must select a hire index as the TCE target
- **Fuel Splits**: Add lines for each fuel type with percentage weights (e.g., 95% VLSFO, 5% MGO)
- **Distances & Times**: Ballast/laden distances, load/discharge rates, turntimes
- **Port Expenses**: Load port, discharge port, misc
- **Margins & Commissions**: Sea margins, address/brokerage commission percentages

### 7. Verify Daily Index Values Exist
Rates can only calculate for dates that have:
- Daily hire index values for the voyage's assigned hire index
- Daily fuel index values for all fuel types in the voyage's fuel splits

## Troubleshooting

**All rates show "-" (None)?**
- Check that all active voyages have a **Daily Hire Index** assigned
- Verify **Daily Index Values** exist for your date range in Admin > Daily Index Values
- Ensure fuel splits are configured and their indices have values

**Missing indices from uploaded file?**
- Check the Indices Display Config to ensure they are marked as active for the vessel size
- Verify the Excel column names match the indices (case-insensitive)
- Re-upload the file or manually add missing indices via Add Index in config

**Calculation errors?**
- Ensure all vessel profiles have at least one speed and fuel profile
- Check that load_rate, discharge_rate, and consumption rates are > 0
- Verify ballast/laden speeds are positive

## Sample Data Setup

To quickly set up sample data:
```bash
python manage.py create_sample_voyages
```

This creates:
- A sample Capesize vessel
- Speed and fuel profiles
- Sample daily index values for the past 30 days
- A configured freight voyage ready for rate calculation
