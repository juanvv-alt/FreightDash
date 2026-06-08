import re
from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal

MONTH_NAMES = {
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
}

VESSEL_CLASS_MAP = {
    'pmax': 'Panamax', 'panamax': 'Panamax',
    'cape': 'Capesize', 'capesize': 'Capesize',
    'supra': 'Supramax', 'supramax': 'Supramax',
    'handy': 'Handysize', 'handysize': 'Handysize',
}


def _last_day(year, month):
    return monthrange(year, month)[1]


def _resolve_quarter(q_num, year):
    starts = {1: 1, 2: 4, 3: 7, 4: 10}
    m_start = starts[q_num]
    m_end = m_start + 2
    return date(year, m_start, 1), date(year, m_end, _last_day(year, m_end))


def _add_months(d, months):
    month = d.month - 1 + months
    year = d.year + month // 12
    month = month % 12 + 1
    day = min(d.day, _last_day(year, month))
    return date(year, month, day)


def parse_ffa_text(text: str, reference_date: date) -> dict:
    """
    Parse raw FFA broker curve text.

    Returns {"vessel_class": str, "periods": [{"label", "period_type",
    "start_date", "end_date", "bid", "offer"}, ...]}.

    period_type is one of: balmo | monthly | quarterly | combined | calendar_year.
    Combined periods (Q34, Jun+Jul, Jun-Dec) are stored but excluded from blending.
    """
    lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
    if not lines:
        return {"vessel_class": "", "periods": []}

    vessel_class = ""
    periods = []
    last_monthly_end = reference_date - timedelta(days=1)
    last_quarterly_end = reference_date - timedelta(days=1)

    for line in lines:
        m = re.match(r'^(.+?)\s+([\d,]+)\s*/\s*([\d,]+)\s*$', line)
        if not m:
            candidate = line.strip().lower()
            if not vessel_class and not re.search(r'\d', candidate):
                vessel_class = VESSEL_CLASS_MAP.get(candidate, line.strip().title())
            continue

        label = m.group(1).strip()
        bid = Decimal(m.group(2).replace(',', ''))
        offer = Decimal(m.group(3).replace(',', ''))
        key = label.lower().replace(' ', '')

        # Balmo
        if key == 'balmo':
            periods.append({
                "label": "Balmo", "period_type": "balmo",
                "start_date": reference_date,
                "end_date": date(reference_date.year, reference_date.month,
                                 _last_day(reference_date.year, reference_date.month)),
                "bid": bid, "offer": offer,
            })
            continue

        # Calendar year: Cal27 …
        cal_m = re.match(r'^cal(\d{2})$', key)
        if cal_m:
            yr = 2000 + int(cal_m.group(1))
            periods.append({
                "label": label, "period_type": "calendar_year",
                "start_date": date(yr, 1, 1), "end_date": date(yr, 12, 31),
                "bid": bid, "offer": offer,
            })
            continue

        # Quarterly: Q1–Q4
        q_m = re.match(r'^q([1-4])$', key)
        if q_m:
            q_num = int(q_m.group(1))
            yr = reference_date.year
            start, end = _resolve_quarter(q_num, yr)
            while end <= last_quarterly_end:
                yr += 1
                start, end = _resolve_quarter(q_num, yr)
            last_quarterly_end = end
            periods.append({
                "label": f"Q{q_num}", "period_type": "quarterly",
                "start_date": start, "end_date": end,
                "bid": bid, "offer": offer,
            })
            continue

        # Combined Q34
        if key == 'q34':
            q3s = [p for p in periods if p['period_type'] == 'quarterly' and p['label'] == 'Q3']
            q4s = [p for p in periods if p['period_type'] == 'quarterly' and p['label'] == 'Q4']
            s = q3s[-1]['start_date'] if q3s else date(reference_date.year, 7, 1)
            e = q4s[-1]['end_date'] if q4s else date(reference_date.year, 12, 31)
            periods.append({"label": "Q34", "period_type": "combined",
                            "start_date": s, "end_date": e, "bid": bid, "offer": offer})
            continue

        # Combined MonA+MonB (Jun+Jul, Jun + Jul)
        plus_m = re.match(r'^([a-z]{3})\+([a-z]{3})$', key)
        if plus_m:
            m1 = MONTH_NAMES.get(plus_m.group(1))
            m2 = MONTH_NAMES.get(plus_m.group(2))
            if m1 and m2:
                yr = reference_date.year
                periods.append({
                    "label": label.replace(' ', ''), "period_type": "combined",
                    "start_date": date(yr, m1, 1),
                    "end_date": date(yr, m2, _last_day(yr, m2)),
                    "bid": bid, "offer": offer,
                })
            continue

        # Combined Mon-Mon (Jun-Dec) — must come before single-month check
        dash_m = re.match(r'^([a-z]{3})-([a-z]{3})$', key)
        if dash_m:
            m1 = MONTH_NAMES.get(dash_m.group(1))
            m2 = MONTH_NAMES.get(dash_m.group(2))
            if m1 and m2:
                yr = reference_date.year
                periods.append({
                    "label": label, "period_type": "combined",
                    "start_date": date(yr, m1, 1),
                    "end_date": date(yr, m2, _last_day(yr, m2)),
                    "bid": bid, "offer": offer,
                })
            continue

        # Monthly: Jan–Dec (exactly 3 letters)
        month_num = MONTH_NAMES.get(key[:3]) if len(key) == 3 else None
        if month_num:
            yr = reference_date.year
            end = date(yr, month_num, _last_day(yr, month_num))
            while end <= last_monthly_end:
                yr += 1
                end = date(yr, month_num, _last_day(yr, month_num))
            start = date(yr, month_num, 1)
            last_monthly_end = end
            periods.append({
                "label": label.title(), "period_type": "monthly",
                "start_date": start, "end_date": end,
                "bid": bid, "offer": offer,
            })

    return {"vessel_class": vessel_class, "periods": periods}
