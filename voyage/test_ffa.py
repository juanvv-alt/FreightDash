from datetime import date
from decimal import Decimal
from django.test import TestCase
from django.urls import reverse


SAMPLE_CURVE = """Pmax
Balmo 20794 / 21248
Jun 20750 / 21100
Jul 21200 / 21400
Jun + Jul 20975 / 21250
Aug 20800 / 21000
Sep 20000 / 20200
Q3 20666 / 20867
Q4 19350 / 19550
Q34 20008 / 20209
Jun-Dec 20114 / 20336
Q1 15000 / 15150
Q2 16250 / 16400
Cal27 15500 / 15650
Cal28 14350 / 14500
Cal29 13800 / 13950"""

REF = date(2026, 6, 8)


class FFAParserTestCase(TestCase):
    def _parse(self, text=SAMPLE_CURVE):
        from .ffa_utils import parse_ffa_text
        return parse_ffa_text(text, REF)

    def test_vessel_class_extracted(self):
        self.assertEqual(self._parse()['vessel_class'], 'Panamax')

    def test_balmo_parsed(self):
        balmo = next(p for p in self._parse()['periods'] if p['period_type'] == 'balmo')
        self.assertEqual(balmo['start_date'], date(2026, 6, 8))
        self.assertEqual(balmo['end_date'], date(2026, 6, 30))
        self.assertEqual(balmo['bid'], Decimal('20794'))
        self.assertEqual(balmo['offer'], Decimal('21248'))

    def test_monthly_jun(self):
        jun = next(p for p in self._parse()['periods']
                   if p['label'] == 'Jun' and p['period_type'] == 'monthly')
        self.assertEqual(jun['start_date'], date(2026, 6, 1))
        self.assertEqual(jun['end_date'], date(2026, 6, 30))
        self.assertEqual(jun['bid'], Decimal('20750'))
        self.assertEqual(jun['offer'], Decimal('21100'))

    def test_quarterly_q3(self):
        q3 = next(p for p in self._parse()['periods'] if p['label'] == 'Q3')
        self.assertEqual(q3['start_date'], date(2026, 7, 1))
        self.assertEqual(q3['end_date'], date(2026, 9, 30))
        self.assertEqual(q3['offer'], Decimal('20867'))

    def test_q1_rolls_to_next_year(self):
        q1 = next(p for p in self._parse()['periods'] if p['label'] == 'Q1')
        self.assertEqual(q1['start_date'], date(2027, 1, 1))
        self.assertEqual(q1['end_date'], date(2027, 3, 31))

    def test_cal27(self):
        cal27 = next(p for p in self._parse()['periods'] if p['label'] == 'Cal27')
        self.assertEqual(cal27['period_type'], 'calendar_year')
        self.assertEqual(cal27['start_date'], date(2027, 1, 1))
        self.assertEqual(cal27['end_date'], date(2027, 12, 31))

    def test_combined_types(self):
        periods = self._parse()['periods']
        q34 = next(p for p in periods if p['label'] == 'Q34')
        self.assertEqual(q34['period_type'], 'combined')
        jundec = next(p for p in periods if p['label'] == 'Jun-Dec')
        self.assertEqual(jundec['period_type'], 'combined')

    def test_total_period_count(self):
        self.assertEqual(len(self._parse()['periods']), 15)
