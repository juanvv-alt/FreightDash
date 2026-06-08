import json as _json
from datetime import date
from decimal import Decimal, Decimal as D

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import FFACurve, FFACurvePeriod


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


class FFABlendingTestCase(TestCase):
    def _periods(self):
        from .ffa_utils import parse_ffa_text
        return parse_ffa_text(SAMPLE_CURVE, REF)['periods']

    def _blend(self, start, months):
        from .ffa_utils import resolve_employment_periods
        return resolve_employment_periods(self._periods(), start, months)

    def test_9m_from_jul1_uses_monthly_over_quarterly(self):
        # Jul/Aug/Sep each have monthly rates which take priority over Q3.
        # Oct-Dec uses Q4, Jan-Mar uses Q1.
        r = self._blend(date(2026, 7, 1), 9)
        self.assertIsNone(r['coverage_warning'])
        labels = [x['label'] for x in r['breakdown']]
        self.assertIn('Jul', labels)   # monthly beats Q3 for Jul
        self.assertIn('Aug', labels)
        self.assertIn('Sep', labels)
        self.assertNotIn('Q3', labels)
        self.assertIn('Q4', labels)
        self.assertIn('Q1', labels)
        # 31+31+30=92 days monthly, 92 days Q4, 90 days Q1 = 274 total
        expected = round((21400*31 + 21000*31 + 20200*30 + 19550*92 + 15150*90) / 274, 2)
        self.assertAlmostEqual(float(r['blended_offer']), float(expected), places=1)

    def test_monthly_priority_over_quarterly(self):
        # Jul has a monthly rate (21400); Q3 also covers Jul (20867).
        # Monthly wins.
        r = self._blend(date(2026, 7, 1), 1)
        self.assertAlmostEqual(float(r['blended_offer']), 21400.0, places=0)

    def test_partial_first_month_days(self):
        r = self._blend(date(2026, 7, 15), 1)
        jul_row = next(x for x in r['breakdown'] if 'Jul' in x['label'])
        self.assertEqual(jul_row['days'], 17)  # Jul 15–31

    def test_coverage_warning_beyond_curve(self):
        r = self._blend(date(2029, 6, 1), 12)
        self.assertIsNotNone(r['coverage_warning'])
        self.assertIsNone(r['blended_offer'])

    def test_end_date_correct(self):
        r = self._blend(date(2026, 7, 1), 3)
        self.assertEqual(r['end_date'], date(2026, 10, 1))

    def test_weights_sum_to_one(self):
        r = self._blend(date(2026, 7, 15), 9)
        self.assertAlmostEqual(sum(x['weight'] for x in r['breakdown']), 1.0, places=4)


class FFAViewsTestCase(TestCase):
    def setUp(self):
        User = get_user_model()
        user = User.objects.create_user(username='testuser', password='testpass')
        self.client.force_login(user)

    def test_get_renders(self):
        r = self.client.get(reverse('voyage:ffa-valuation'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'ffa-curve-textarea')

    def test_post_parse_returns_periods(self):
        r = self.client.post(
            reverse('voyage:ffa-valuation'),
            {'action': 'parse', 'raw_text': SAMPLE_CURVE},
        )
        self.assertEqual(r.status_code, 200)
        data = _json.loads(r.content)
        self.assertEqual(data['vessel_class'], 'Panamax')
        self.assertEqual(len(data['periods']), 15)

    def test_post_save_persists(self):
        parse_r = self.client.post(
            reverse('voyage:ffa-valuation'),
            {'action': 'parse', 'raw_text': SAMPLE_CURVE},
        )
        periods = _json.loads(parse_r.content)['periods']
        save_r = self.client.post(
            reverse('voyage:ffa-valuation'),
            _json.dumps({'action': 'save', 'raw_text': SAMPLE_CURVE,
                         'vessel_class': 'Panamax', 'periods': periods}),
            content_type='application/json',
        )
        self.assertEqual(save_r.status_code, 200)
        data = _json.loads(save_r.content)
        self.assertIn('curve_id', data)
        self.assertTrue(FFACurve.objects.filter(id=data['curve_id']).exists())
        self.assertEqual(FFACurvePeriod.objects.filter(curve_id=data['curve_id']).count(), 15)


class FFACalculateTestCase(TestCase):
    def setUp(self):
        User = get_user_model()
        user = User.objects.create_user(username='calcuser', password='testpass')
        self.client.force_login(user)
        self.curve = FFACurve.objects.create(vessel_class='Panamax', raw_text='test')
        for label, ptype, s, e, bid, offer in [
            ('Q3', 'quarterly', date(2026, 7, 1), date(2026, 9, 30), D('20666'), D('20867')),
            ('Q4', 'quarterly', date(2026, 10, 1), date(2026, 12, 31), D('19350'), D('19550')),
            ('Q1', 'quarterly', date(2027, 1, 1), date(2027, 3, 31), D('15000'), D('15150')),
        ]:
            FFACurvePeriod.objects.create(
                curve=self.curve, label=label, period_type=ptype,
                start_date=s, end_date=e, bid=bid, offer=offer,
            )

    def _calc(self, payload):
        return self.client.post(
            reverse('voyage:ffa-valuation-calculate'),
            _json.dumps(payload),
            content_type='application/json',
        )

    def test_blended_9m_from_jul1(self):
        r = self._calc({'curve_id': self.curve.id, 'delivery_date': '2026-07-01',
                        'period_months': 9, 'vessel_ids': []})
        data = _json.loads(r.content)
        self.assertIsNone(data['coverage_warning'])
        # Only quarterly periods in this test curve; blending is day-weighted:
        # Q3: Jul-Sep = 92 days, Q4: Oct-Dec = 92 days, Q1: Jan-Mar = 90 days (274 total)
        expected = round((20867 * 92 + 19550 * 92 + 15150 * 90) / 274, 2)
        self.assertAlmostEqual(data['blended_offer'], float(expected), places=1)

    def test_coverage_warning(self):
        r = self._calc({'curve_id': self.curve.id, 'delivery_date': '2030-01-01',
                        'period_months': 3, 'vessel_ids': []})
        data = _json.loads(r.content)
        self.assertIsNotNone(data['coverage_warning'])
        self.assertIsNone(data['blended_offer'])

    def test_timeline_no_combined(self):
        r = self._calc({'curve_id': self.curve.id, 'delivery_date': '2026-07-01',
                        'period_months': 3, 'vessel_ids': []})
        data = _json.loads(r.content)
        self.assertNotIn('combined', {t['period_type'] for t in data['timeline']})
