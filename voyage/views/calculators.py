import logging
from bisect import bisect_right
from datetime import timedelta

from django.db import DatabaseError, ProgrammingError
from django.db.utils import OperationalError
from django.shortcuts import redirect, render
from django.utils import timezone

from ..models import (
    DailyIndexValue,
    FreightVoyage,
    RouteParameters,
    VesselFuelConsumption,
)
from ..forms import TCECalculatorForm
from ..calculators import (
    calculate_fuel_and_days,
    calculate_tce,
    calculate_freight_from_tce,
    calculate_vessel_comparison,
)


logger = logging.getLogger(__name__)


def _resolve_intake(voyage):
    if voyage.intake_mode == 'manual':
        return max(voyage.intake_manual, 0)

    vessel = voyage.vessel
    if not vessel:
        return 0

    draft_limit = voyage.draft_limit or vessel.draft
    draft_ratio = min(draft_limit / vessel.draft, 1) if vessel.draft else 1
    draft_adjusted_dwt = vessel.dwt * draft_ratio

    if voyage.stowage_factor and vessel.grain_capacity:
        capacity_limited = vessel.grain_capacity / voyage.stowage_factor
        return max(min(draft_adjusted_dwt, capacity_limited), 0)

    return max(draft_adjusted_dwt, 0)


def _select_speed_profile(voyage):
    if voyage.speed_profile:
        return voyage.speed_profile

    default_profile = voyage.vessel.speed_profiles.filter(is_default=True).first()
    if default_profile:
        return default_profile

    return voyage.vessel.speed_profiles.order_by('name').first()


def _total_consumption_by_mode(voyage):
    fuel_profile = voyage.fuel_profile or voyage.vessel.fuel_profiles.filter(is_default=True).first()
    if not fuel_profile:
        fuel_profile = voyage.vessel.fuel_profiles.order_by('name').first()

    lines = list(VesselFuelConsumption.objects.filter(fuel_profile=fuel_profile)) if fuel_profile else []
    sea_total = sum(line.sea_consumption for line in lines)
    port_total = sum(line.port_consumption for line in lines)
    return sea_total, port_total


def _blended_fuel_price(voyage, date_value):
    splits = list(voyage.fuel_splits.select_related('fuel_index').all())
    if not splits:
        return None

    lookup = {
        value.index_id: value.value
        for value in DailyIndexValue.objects.filter(
            index_id__in=[line.fuel_index_id for line in splits],
            date=date_value,
        )
    }

    total_weight = 0.0
    total_price = 0.0
    for line in splits:
        index_price = lookup.get(line.fuel_index_id)
        if index_price is None or line.weight_pct <= 0:
            continue
        total_weight += line.weight_pct
        total_price += index_price * line.weight_pct

    if total_weight <= 0:
        return None

    return total_price / total_weight


def freight_matrix(request):
    today = timezone.localdate()
    default_start = today - timedelta(days=30)

    start_date_raw = request.GET.get('start_date', default_start.isoformat())
    end_date_raw = request.GET.get('end_date', today.isoformat())

    try:
        start_date = timezone.datetime.strptime(start_date_raw, '%Y-%m-%d').date()
    except ValueError:
        start_date = default_start

    try:
        end_date = timezone.datetime.strptime(end_date_raw, '%Y-%m-%d').date()
    except ValueError:
        end_date = today

    if start_date > end_date:
        start_date, end_date = end_date, start_date

    date_rows = [
        end_date - timedelta(days=offset)
        for offset in range((end_date - start_date).days + 1)
        if (end_date - timedelta(days=offset)).weekday() < 5
    ]

    voyages = list(
        FreightVoyage.objects.filter(is_active=True)
        .select_related('vessel', 'speed_profile', 'fuel_profile', 'daily_hire_index')
        .prefetch_related('fuel_splits__fuel_index', 'vessel__speed_profiles', 'vessel__fuel_profiles')
        .order_by('name')
    )

    warnings = []

    if not voyages:
        warnings.append('No active voyages configured. Add voyages in Django admin.')
        logger.warning('Freight matrix: No active voyages found')

    hire_index_ids = [v.daily_hire_index_id for v in voyages if v.daily_hire_index_id]
    voyages_without_hire_index = [v.name for v in voyages if not v.daily_hire_index_id]
    if voyages_without_hire_index:
        warnings.append(f'Voyages without daily hire index assignment: {", ".join(voyages_without_hire_index)}')
        logger.warning(f'Freight matrix: Voyages without hire index: {voyages_without_hire_index}')

    hire_values = DailyIndexValue.objects.filter(index_id__in=hire_index_ids, date__gte=start_date, date__lte=end_date)
    hire_map = {(v.index_id, v.date): v.value for v in hire_values}

    if hire_index_ids and not hire_map:
        warnings.append(f'No daily hire index values found for date range {start_date} to {end_date}. Check uploaded index data.')
        logger.warning(f'Freight matrix: No hire values found for indices {hire_index_ids} in date range')
    # Prepare a time-series cache for relevant index ids so we can fall back
    # to the most recent available value on or before a given date.
    needed_index_ids = set(hire_index_ids)
    for v in voyages:
        for line in v.fuel_splits.all():
            if line.fuel_index_id:
                needed_index_ids.add(line.fuel_index_id)

    index_dates = {}
    index_values = {}
    if needed_index_ids:
        qs = DailyIndexValue.objects.filter(index_id__in=needed_index_ids, date__lte=end_date).order_by('date')
        for val in qs:
            idx = val.index_id
            index_dates.setdefault(idx, []).append(val.date)
            index_values.setdefault(idx, []).append(val.value)
    matrix_rows = []
    # helper to find latest value for index_id on or before date_value
    def _latest_value(idx_id, date_value):
        dates = index_dates.get(idx_id)
        if not dates:
            return None
        # find rightmost date <= date_value
        pos = bisect_right(dates, date_value) - 1
        if pos < 0:
            return None
        return index_values[idx_id][pos]

    for row_date in date_rows:
        rates = {}
        for voyage in voyages:
            if not voyage.daily_hire_index_id:
                rates[voyage.name] = None
                continue

            target_tce = hire_map.get((voyage.daily_hire_index_id, row_date))
            if target_tce is None and voyage.daily_hire_index_id:
                target_tce = _latest_value(voyage.daily_hire_index_id, row_date)

            blended_fuel_price = _blended_fuel_price(voyage, row_date)
            # if blended price is missing for the exact date, try to compute
            # using the latest available fuel index values on or before row_date
            if blended_fuel_price is None:
                splits = list(voyage.fuel_splits.all())
                if splits:
                    total_weight = 0.0
                    total_price = 0.0
                    for line in splits:
                        idx_price = _latest_value(line.fuel_index_id, row_date)
                        if idx_price is None or line.weight_pct <= 0:
                            continue
                        total_weight += line.weight_pct
                        total_price += idx_price * line.weight_pct
                    if total_weight > 0:
                        blended_fuel_price = total_price / total_weight
            speed = _select_speed_profile(voyage)

            # track whether we used fallback (earlier-date) values
            hire_used_fallback = False
            fuel_used_fallback = False

            if (
                target_tce is None
                or blended_fuel_price is None
                or not speed
                or speed.ballast_speed <= 0
                or speed.laden_speed <= 0
            ):
                # try fallbacks where possible
                if target_tce is None and voyage.daily_hire_index_id:
                    target_tce = _latest_value(voyage.daily_hire_index_id, row_date)
                    if target_tce is not None:
                        hire_used_fallback = True

                if blended_fuel_price is None:
                    splits = list(voyage.fuel_splits.all())
                    if splits:
                        total_weight = 0.0
                        total_price = 0.0
                        for line in splits:
                            idx_price = _latest_value(line.fuel_index_id, row_date)
                            if idx_price is None or line.weight_pct <= 0:
                                continue
                            total_weight += line.weight_pct
                            total_price += idx_price * line.weight_pct
                        if total_weight > 0:
                            blended_fuel_price = total_price / total_weight
                            fuel_used_fallback = True

            # if still missing critical inputs, skip
            if (
                target_tce is None
                or blended_fuel_price is None
                or not speed
                or speed.ballast_speed <= 0
                or speed.laden_speed <= 0
            ):
                rates[voyage.name] = None
                continue

            intake = _resolve_intake(voyage)
            if intake <= 0 or voyage.load_rate <= 0 or voyage.discharge_rate <= 0:
                rates[voyage.name] = None
                continue

            sea_consumption, port_consumption = _total_consumption_by_mode(voyage)
            if sea_consumption <= 0:
                rates[voyage.name] = None
                continue

            ballast_margin = voyage.sea_margin_ballast_pct / 100.0
            laden_margin = (
                voyage.sea_margin_ballast_pct / 100.0
                if voyage.apply_same_sea_margin
                else voyage.sea_margin_laden_pct / 100.0
            )

            ballast_days = ((voyage.ballast_distance / speed.ballast_speed) / 24.0) * (1 + ballast_margin)
            laden_days = ((voyage.laden_distance / speed.laden_speed) / 24.0) * (1 + laden_margin)
            load_days = (intake / voyage.load_rate) + (voyage.turntime_load_hours / 24.0)
            discharge_days = (intake / voyage.discharge_rate) + (voyage.turntime_discharge_hours / 24.0)
            voyage_days = ballast_days + laden_days + load_days + discharge_days

            if voyage_days <= 0:
                rates[voyage.name] = None
                continue

            fuel_mt = ((ballast_days + laden_days) * sea_consumption) + ((load_days + discharge_days) * port_consumption)
            total_port_expenses = voyage.port_exp_load_port + voyage.port_exp_discharge_port + voyage.misc_expenses
            commission = (voyage.address_commission_pct + voyage.brokerage_commission_pct) / 100.0

            denominator = intake * (1 - commission)
            if denominator <= 0:
                rates[voyage.name] = None
                continue

            freight_rate = ((target_tce * voyage_days) + total_port_expenses + (fuel_mt * blended_fuel_price)) / denominator
            rates[voyage.name] = {
                'value': round(freight_rate, 2),
                'asterisk': bool(hire_used_fallback or fuel_used_fallback),
            }

        matrix_rows.append({'date': row_date, 'rates': rates})

    context = {
        'start_date': start_date,
        'end_date': end_date,
        'voyages': voyages,
        'matrix_rows': matrix_rows,
        'warnings': warnings,
    }
    return render(request, 'voyage/freight_matrix.html', context)


def tce_calculator(request):
    """
    Main TCE Calculator viewer.
    Handles route selection and TCE/Freight calculations.
    """
    try:
        calculated_tce = None
        calculated_freight = None
        db_not_ready = False
        db_error_message = ""
        routes = []
        route_choices = []

        try:
            routes = list(RouteParameters.objects.all())
            route_choices = [(str(route.id), route.route) for route in routes]
        except (ProgrammingError, OperationalError) as exc:
            routes = []
            route_choices = []
            db_not_ready = True
            db_error_message = str(exc)

        form_initial = {}

        if request.method == 'POST' and not db_not_ready:
            post_data = request.POST.copy()
            route_id = post_data.get('route')

            if route_id:
                try:
                    route = RouteParameters.objects.get(id=route_id)
                    route_values = {
                        'route': str(route.id),
                        'ballast_distance': route.ballast_distance,
                        'laden_distance': route.laden_distance,
                        'intake': route.intake,
                        'load_rate': route.load_rate,
                        'discharge_rate': route.discharge_rate,
                        'turntime_hours': route.turntime_hours,
                        'port_exp_load_port': route.port_exp_load_port,
                        'port_exp_discharge_port': route.port_exp_discharge_port,
                        'freight_commission_pct': route.freight_commission_pct,
                        'sea_margin_pct': route.sea_margin_pct,
                        'ballast_speed': route.ballast_speed,
                        'laden_speed': route.laden_speed,
                        'ballast_consumption': route.ballast_consumption,
                        'laden_consumption': route.laden_consumption,
                        'port_consumption': route.port_consumption,
                    }
                    form_initial.update(route_values)

                    if 'calc_tce' not in post_data and 'calc_freight' not in post_data:
                        for key, value in route_values.items():
                            post_data[key] = value
                except (RouteParameters.DoesNotExist, DatabaseError):
                    pass

            form = TCECalculatorForm(post_data, route_choices=route_choices)

            if form.is_valid():
                # Calculate common values used by both calculators.
                data = form.cleaned_data
                common_data = calculate_fuel_and_days(
                    ballast_distance=data['ballast_distance'],
                    laden_distance=data['laden_distance'],
                    intake=data['intake'],
                    load_rate=data['load_rate'],
                    discharge_rate=data['discharge_rate'],
                    turntime_hours=data['turntime_hours'],
                    port_exp_load_port=data['port_exp_load_port'],
                    port_exp_discharge_port=data['port_exp_discharge_port'],
                    freight_commission_pct=data['freight_commission_pct'],
                    sea_margin_pct=data['sea_margin_pct'],
                    ballast_speed=data['ballast_speed'],
                    laden_speed=data['laden_speed'],
                    ballast_consumption=data['ballast_consumption'],
                    laden_consumption=data['laden_consumption'],
                    port_consumption=data['port_consumption'],
                )

                if 'calc_tce' in request.POST:
                    calculated_tce = calculate_tce(
                        freight_rate=data['freight_rate'],
                        fuel_price=data['fuel_price'],
                        intake=data['intake'],
                        common_data=common_data
                    )
                    form_initial['tce_field'] = calculated_tce
                elif 'calc_freight' in request.POST:
                    calculated_freight = calculate_freight_from_tce(
                        target_tce=data['tce_field'],
                        fuel_price=data['fuel_price'],
                        intake=data['intake'],
                        common_data=common_data
                    )
                    form_initial['freight_rate'] = calculated_freight
        else:
            if routes:
                first_route = routes[0]
                form_initial = {
                    'route': str(first_route.id),
                    'ballast_distance': first_route.ballast_distance,
                    'laden_distance': first_route.laden_distance,
                    'intake': first_route.intake,
                    'load_rate': first_route.load_rate,
                    'discharge_rate': first_route.discharge_rate,
                    'turntime_hours': first_route.turntime_hours,
                    'port_exp_load_port': first_route.port_exp_load_port,
                    'port_exp_discharge_port': first_route.port_exp_discharge_port,
                    'freight_commission_pct': first_route.freight_commission_pct,
                    'sea_margin_pct': first_route.sea_margin_pct,
                    'ballast_speed': first_route.ballast_speed,
                    'laden_speed': first_route.laden_speed,
                    'ballast_consumption': first_route.ballast_consumption,
                    'laden_consumption': first_route.laden_consumption,
                    'port_consumption': first_route.port_consumption,
                }
            form = TCECalculatorForm(route_choices=route_choices)

        for key, value in form_initial.items():
            if key in form.fields:
                form.fields[key].initial = value

        context = {
            'form': form,
            'routes': routes,
            'calculated_tce': calculated_tce,
            'calculated_freight': calculated_freight,
            'db_not_ready': db_not_ready,
            'db_error_message': db_error_message,
        }
        return render(request, 'voyage/tce_calculator.html', context)
    except Exception as exc:
        logger.exception("Unhandled error in tce_calculator")
        form = TCECalculatorForm(route_choices=[])
        context = {
            'form': form,
            'routes': [],
            'calculated_tce': None,
            'calculated_freight': None,
            'db_not_ready': True,
            'db_error_message': str(exc),
        }
        return render(request, 'voyage/tce_calculator.html', context, status=200)


def vessel_compare(request):
    from ..models import ComparisonVessel, ComparisonVoyage, VesselCompareConfig, VesselVoyageIntake

    def _f(val, default=0.0):
        try:
            return float(val)
        except (ValueError, TypeError):
            return float(default)

    def _run_calc(cfg, voyages_qs, vessels_qs):
        voyages = [
            {'name': voy.name, 'ballast_dist': voy.ballast_dist, 'laden_dist': voy.laden_dist,
             'load_rate': voy.load_rate, 'dis_rate': voy.dis_rate,
             'load_factor': voy.load_factor, 'dis_factor': voy.dis_factor,
             'turntimes_hours': voy.turntimes_hours,
             'port_exp': voy.port_exp, 'various_exp': voy.various_exp}
            for voy in voyages_qs
        ]
        # Build intake map: {vessel_id: {voyage_id: intake}}
        intake_map = {}
        for vi in VesselVoyageIntake.objects.filter(
            vessel__in=vessels_qs, voyage__in=voyages_qs
        ).select_related('vessel', 'voyage'):
            intake_map.setdefault(vi.vessel_id, {})[vi.voyage_id] = vi.intake

        vessels = []
        for v in vessels_qs:
            v_intakes = intake_map.get(v.id, {})
            intakes = [v_intakes.get(voy.id, v.default_intake) for voy in voyages_qs]
            vessels.append({
                'name': v.name, 'intakes': intakes,
                'laden_speed': v.laden_speed, 'ballast_speed': v.ballast_speed,
                'laden_cons': v.laden_cons, 'ballast_cons': v.ballast_cons,
                'port_cons': v.port_cons,
            })

        global_inputs = {'hire': cfg.hire, 'ifo_price': cfg.ifo_price,
                         'mgo_price': cfg.mgo_price, 'weather_factor': cfg.weather_factor}
        r = calculate_vessel_comparison(global_inputs, voyages, vessels)
        r['vessel_summary'] = [
            {'name': name, 'wa': wa,
             'pct': wa * 100 if wa is not None else None,
             'pct_delta': (wa - 1) * 100 if wa is not None else None}
            for name, wa in zip(r['vessels'], r['weighted_avgs'])
        ]
        return r

    cfg = VesselCompareConfig.get()

    if request.method == 'POST':
        action = request.POST.get('action', '')

        if action == 'update_config':
            cfg.hire = _f(request.POST.get('hire'), cfg.hire)
            cfg.ifo_price = _f(request.POST.get('ifo_price'), cfg.ifo_price)
            cfg.mgo_price = _f(request.POST.get('mgo_price'), cfg.mgo_price)
            cfg.weather_factor = _f(request.POST.get('weather_factor'), cfg.weather_factor)
            cfg.save()
            return redirect('voyage:vessel_compare')

        elif action == 'add_voyage':
            name = request.POST.get('new_voy_name', '').strip()
            if name:
                next_order = ComparisonVoyage.objects.count()
                voy = ComparisonVoyage.objects.create(
                    name=name, order=next_order,
                    ballast_dist=_f(request.POST.get('new_voy_ballast_dist'), 5000),
                    laden_dist=_f(request.POST.get('new_voy_laden_dist'), 5000),
                    load_rate=_f(request.POST.get('new_voy_load_rate'), 10000),
                    dis_rate=_f(request.POST.get('new_voy_dis_rate'), 10000),
                    load_factor=_f(request.POST.get('new_voy_load_factor'), 1.0),
                    dis_factor=_f(request.POST.get('new_voy_dis_factor'), 1.0),
                    turntimes_hours=_f(request.POST.get('new_voy_turntimes'), 36),
                    port_exp=_f(request.POST.get('new_voy_port_exp'), 100000),
                    various_exp=_f(request.POST.get('new_voy_various_exp'), 10000),
                )
                # Create default intake records for all existing vessels
                default_intake = _f(request.POST.get('new_voy_default_intake'), 79000)
                for vessel in ComparisonVessel.objects.all():
                    VesselVoyageIntake.objects.get_or_create(
                        vessel=vessel, voyage=voy,
                        defaults={'intake': default_intake},
                    )
            return redirect('voyage:vessel_compare')

        elif action == 'edit_voyage':
            vid = request.POST.get('voyage_id')
            try:
                voy = ComparisonVoyage.objects.get(pk=int(vid))
                voy.name = request.POST.get('edit_voy_name', voy.name).strip() or voy.name
                voy.ballast_dist = _f(request.POST.get('edit_voy_ballast_dist'), voy.ballast_dist)
                voy.laden_dist = _f(request.POST.get('edit_voy_laden_dist'), voy.laden_dist)
                voy.load_rate = _f(request.POST.get('edit_voy_load_rate'), voy.load_rate)
                voy.dis_rate = _f(request.POST.get('edit_voy_dis_rate'), voy.dis_rate)
                voy.load_factor = _f(request.POST.get('edit_voy_load_factor'), voy.load_factor)
                voy.dis_factor = _f(request.POST.get('edit_voy_dis_factor'), voy.dis_factor)
                voy.turntimes_hours = _f(request.POST.get('edit_voy_turntimes'), voy.turntimes_hours)
                voy.port_exp = _f(request.POST.get('edit_voy_port_exp'), voy.port_exp)
                voy.various_exp = _f(request.POST.get('edit_voy_various_exp'), voy.various_exp)
                voy.save()
            except (ComparisonVoyage.DoesNotExist, ValueError):
                pass
            return redirect('voyage:vessel_compare')

        elif action == 'delete_voyage':
            vid = request.POST.get('voyage_id')
            try:
                ComparisonVoyage.objects.get(pk=int(vid)).delete()
            except (ComparisonVoyage.DoesNotExist, ValueError):
                pass
            return redirect('voyage:vessel_compare')

        elif action == 'add_vessel':
            name = request.POST.get('new_name', '').strip()
            if name:
                default_intake = _f(request.POST.get('new_default_intake'), 79000)
                next_order = ComparisonVessel.objects.count()
                vessel = ComparisonVessel.objects.create(
                    name=name, order=next_order,
                    default_intake=default_intake,
                    laden_speed=_f(request.POST.get('new_laden_speed'), 12),
                    ballast_speed=_f(request.POST.get('new_ballast_speed'), 12.5),
                    laden_cons=_f(request.POST.get('new_laden_cons'), 22),
                    ballast_cons=_f(request.POST.get('new_ballast_cons'), 23),
                    port_cons=_f(request.POST.get('new_port_cons'), 4.5),
                )
                # Create intake records for each voyage
                for voy in ComparisonVoyage.objects.all():
                    intake_val = _f(request.POST.get(f'new_intake_{voy.id}'), default_intake)
                    VesselVoyageIntake.objects.get_or_create(
                        vessel=vessel, voyage=voy,
                        defaults={'intake': intake_val},
                    )
            return redirect('voyage:vessel_compare')

        elif action == 'edit_vessel':
            vid = request.POST.get('vessel_id')
            try:
                v = ComparisonVessel.objects.get(pk=int(vid))
                v.name = request.POST.get('edit_name', v.name).strip() or v.name
                v.default_intake = _f(request.POST.get('edit_default_intake'), v.default_intake)
                v.laden_speed = _f(request.POST.get('edit_laden_speed'), v.laden_speed)
                v.ballast_speed = _f(request.POST.get('edit_ballast_speed'), v.ballast_speed)
                v.laden_cons = _f(request.POST.get('edit_laden_cons'), v.laden_cons)
                v.ballast_cons = _f(request.POST.get('edit_ballast_cons'), v.ballast_cons)
                v.port_cons = _f(request.POST.get('edit_port_cons'), v.port_cons)
                v.save()
                # Update per-voyage intakes
                for voy in ComparisonVoyage.objects.all():
                    intake_val = _f(request.POST.get(f'edit_intake_{voy.id}'), v.default_intake)
                    VesselVoyageIntake.objects.update_or_create(
                        vessel=v, voyage=voy,
                        defaults={'intake': intake_val},
                    )
            except (ComparisonVessel.DoesNotExist, ValueError):
                pass
            return redirect('voyage:vessel_compare')

        elif action == 'delete_vessel':
            vid = request.POST.get('vessel_id')
            try:
                v = ComparisonVessel.objects.get(pk=int(vid))
                if not v.is_standard:
                    v.delete()
            except (ComparisonVessel.DoesNotExist, ValueError):
                pass
            return redirect('voyage:vessel_compare')

    voyages_qs = ComparisonVoyage.objects.all()
    vessels_qs = ComparisonVessel.objects.all()

    # Build intake lookup for template: {vessel_id: {voyage_id: intake}}
    intake_map = {}
    for vi in VesselVoyageIntake.objects.filter(
        vessel__in=vessels_qs, voyage__in=voyages_qs
    ).select_related('vessel', 'voyage'):
        intake_map.setdefault(vi.vessel_id, {})[vi.voyage_id] = vi.intake

    # Enrich vessels with per-voyage intake list for template
    vessels_with_intakes = []
    for v in vessels_qs:
        v_intakes = intake_map.get(v.id, {})
        vessels_with_intakes.append({
            'obj': v,
            'intakes': {voy.id: v_intakes.get(voy.id, v.default_intake) for voy in voyages_qs},
        })

    results = None
    error = None
    if vessels_qs.exists() and voyages_qs.exists():
        try:
            results = _run_calc(cfg, voyages_qs, vessels_qs)
        except Exception as exc:
            logger.exception("Error in vessel_compare calculation")
            error = str(exc)

    context = {
        'cfg': cfg,
        'voyages': voyages_qs,
        'vessels': vessels_qs,
        'vessels_with_intakes': vessels_with_intakes,
        'results': results,
        'error': error,
    }
    return render(request, 'voyage/vessel_compare.html', context)
