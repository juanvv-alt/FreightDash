import json
from datetime import date

from django.http import JsonResponse
from django.shortcuts import render

from ..models import (
    ComparisonVessel,
    FFACurve,
    FFACurvePeriod,
)
from ..ffa_utils import parse_ffa_text, resolve_employment_periods
from ..calculators import calculate_vessel_comparison


def ffa_valuation(request):
    if request.method == 'POST':
        ct = request.content_type or ''
        if 'application/json' in ct:
            body = json.loads(request.body)
        else:
            body = request.POST
        action = body.get('action')

        if action == 'parse':
            result = parse_ffa_text(body.get('raw_text', ''), date.today())
            return JsonResponse({
                'vessel_class': result['vessel_class'],
                'periods': [
                    {
                        'label': p['label'], 'period_type': p['period_type'],
                        'start_date': p['start_date'].isoformat(),
                        'end_date': p['end_date'].isoformat(),
                        'bid': str(p['bid']), 'offer': str(p['offer']),
                    }
                    for p in result['periods']
                ],
            })

        if action == 'save':
            raw_text = body.get('raw_text', '')
            vessel_class = body.get('vessel_class', '')
            periods_data = body.get('periods', [])
            if isinstance(periods_data, str):
                periods_data = json.loads(periods_data)
            curve = FFACurve.objects.create(vessel_class=vessel_class, raw_text=raw_text)
            FFACurvePeriod.objects.bulk_create([
                FFACurvePeriod(
                    curve=curve, label=p['label'], period_type=p['period_type'],
                    start_date=p['start_date'], end_date=p['end_date'],
                    bid=p['bid'], offer=p['offer'],
                )
                for p in periods_data
            ])
            return JsonResponse({'curve_id': curve.id, 'status': 'saved'})

    curve = FFACurve.objects.prefetch_related('periods').first()
    vessels = ComparisonVessel.objects.order_by('name')
    return render(request, 'voyage/ffa_valuation.html', {
        'curve': curve,
        'vessels': vessels,
        'today': date.today(),
    })


def ffa_valuation_calculate(request):
    data = json.loads(request.body)
    delivery_date = date.fromisoformat(data['delivery_date'])
    period_months = int(data.get('period_months', 1))
    vessel_ids = [int(v) for v in data.get('vessel_ids', [])]

    try:
        curve = FFACurve.objects.prefetch_related('periods').get(id=data['curve_id'])
    except FFACurve.DoesNotExist:
        return JsonResponse({'error': 'Curve not found'}, status=404)

    curve_periods = [
        {
            'label': p.label, 'period_type': p.period_type,
            'start_date': p.start_date, 'end_date': p.end_date,
            'bid': p.bid, 'offer': p.offer,
        }
        for p in curve.periods.all()
    ]

    result = resolve_employment_periods(curve_periods, delivery_date, period_months)
    employment_end = result['end_date']

    timeline = [
        {
            'label': p['label'], 'offer': float(p['offer']),
            'start': p['start_date'].isoformat(), 'end': p['end_date'].isoformat(),
            'period_type': p['period_type'],
            'in_window': p['start_date'] < employment_end and p['end_date'] >= delivery_date,
        }
        for p in curve_periods if p['period_type'] != 'combined'
    ]

    vessels_out = []
    if vessel_ids and result['blended_offer'] is not None:
        try:
            from ..models import (ComparisonVoyage, VesselCompareConfig,
                                  VesselVoyageIntake)
            cfg = VesselCompareConfig.objects.first()
            voyages_qs = list(ComparisonVoyage.objects.all())
            bki = ComparisonVessel.objects.filter(is_standard=True).first()
            selected = list(ComparisonVessel.objects.filter(
                id__in=vessel_ids).exclude(is_standard=True))
            all_v = ([bki] if bki else []) + selected

            intake_map = {}
            for vi in VesselVoyageIntake.objects.filter(
                vessel__in=all_v, voyage__in=voyages_qs
            ).select_related('vessel', 'voyage'):
                intake_map.setdefault(vi.vessel_id, {})[vi.voyage_id] = vi.intake

            voyages = [
                {
                    'name': v.name, 'ballast_dist': v.ballast_dist,
                    'laden_dist': v.laden_dist, 'load_rate': v.load_rate,
                    'dis_rate': v.dis_rate, 'load_factor': v.load_factor,
                    'dis_factor': v.dis_factor,
                    'turntimes_hours': v.turntimes_hours,
                    'port_exp': v.port_exp, 'various_exp': v.various_exp,
                }
                for v in voyages_qs
            ]
            vessels_input = []
            for v in all_v:
                v_intakes = intake_map.get(v.id, {})
                vessels_input.append({
                    'name': v.name,
                    'intakes': [v_intakes.get(voy.id, v.default_intake)
                                for voy in voyages_qs],
                    'laden_speed': v.laden_speed,
                    'ballast_speed': v.ballast_speed,
                    'laden_cons': v.laden_cons,
                    'ballast_cons': v.ballast_cons,
                    'port_cons': v.port_cons,
                })

            if voyages and vessels_input and cfg:
                vc = calculate_vessel_comparison(
                    {
                        'hire': cfg.hire, 'ifo_price': cfg.ifo_price,
                        'mgo_price': cfg.mgo_price,
                        'weather_factor': cfg.weather_factor,
                    },
                    voyages,
                    vessels_input,
                )
                blended = float(result['blended_offer'])
                for i, (name, wa) in enumerate(
                    zip(vc['vessels'], vc['weighted_avgs'])
                ):
                    vessel_obj = all_v[i]
                    if vessel_obj.id not in vessel_ids:
                        continue
                    if wa is None:
                        continue
                    vessels_out.append({
                        'id': vessel_obj.id,
                        'name': name,
                        'pct': round(wa * 100, 2),
                        'adjusted_rate': round(blended * wa, 2),
                    })
        except Exception:
            pass  # vessel calc is best-effort; don't let it break the main result

    return JsonResponse({
        'blended_offer': (float(result['blended_offer'])
                          if result['blended_offer'] is not None else None),
        'delivery_date': delivery_date.isoformat(),
        'end_date': result['end_date'].isoformat(),
        'coverage_warning': result.get('coverage_warning'),
        'timeline': timeline,
        'breakdown': [
            {
                'label': r['label'], 'period_type': r.get('period_type', ''),
                'bid': float(r['bid']), 'offer': float(r['offer']),
                'days': r['days'], 'weight': r['weight'],
                'contribution': round(float(r['offer']) * r['weight'], 2),
            }
            for r in result.get('breakdown', [])
        ],
        'vessels': vessels_out,
    })
