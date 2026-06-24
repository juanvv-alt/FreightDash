from datetime import datetime


def _parse_date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return None

        formats = [
            '%Y-%m-%d',
            '%d/%m/%Y',
            '%m/%d/%Y',
            '%d-%m-%Y',
            '%m-%d-%Y',
            '%b %d, %Y',
            '%B %d, %Y',
            '%d %b %Y',
            '%d %B %Y',
            '%Y/%m/%d',
        ]

        for fmt in formats:
            try:
                return datetime.strptime(cleaned, fmt).date()
            except ValueError:
                continue

        normalized = cleaned.replace('/', '-').replace('.', '-').lower()
        month_names = {
            'jan': '01',
            'feb': '02',
            'mar': '03',
            'apr': '04',
            'may': '05',
            'jun': '06',
            'jul': '07',
            'aug': '08',
            'sep': '09',
            'oct': '10',
            'nov': '11',
            'dec': '12',
        }
        for month_name, month_num in month_names.items():
            if month_name in normalized:
                normalized = normalized.replace(month_name, month_num)

        for fmt in formats:
            try:
                return datetime.strptime(normalized, fmt).date()
            except ValueError:
                continue

    return None
