from datetime import timedelta

from django.shortcuts import redirect, render
from django.db import DatabaseError, ProgrammingError
from django.db.utils import OperationalError
from django.utils import timezone
import logging
from .models import RouteParameters
from .forms import TCECalculatorForm
from .calculators import (
    calculate_fuel_and_days,
    calculate_tce,
    calculate_freight_from_tce
)


logger = logging.getLogger(__name__)


VESSEL_INDEX_GROUPS = {
    'capesize': {
        'label': 'Capesize',
        'indices': [
            'C2', 'C3', 'C5', 'C7', 'C8_14', 'C9_14', 'C10_14', 'C14', 'C16', 'C17',
            'BCI 5TC', 'BCI 4TC', 'BCI Index', 'Minicape (Old)', 'Minicape (Broker)',
            'Minicape (AVG)', 'Forward Capesize (Current)', 'Forward Capesize (Next MTH)',
            'Forward Panamax (Current)', 'Forward Panamax (Next Mth)',
            'Forward Minicape (Old) (Current)', 'Forward Minicape (Old) (Next Mth)',
            'Forward Minicape (Broker) (Current)', 'Forward Minicape (Broker) (Next Mth)',
        ],
    },
    'panamax': {
        'label': 'Panamax',
        'indices': ['P1A_82', 'P2A_82', 'P3A_82', 'P4A_82', 'P5_82', 'BPI 82TC', 'BPI Index'],
    },
    'supramax': {
        'label': 'Supramax',
        'indices': ['S1B_58', 'S1C_58', 'S2_58', 'S3_58', 'S4A_58', 'S4B_58', 'BSI 58TC', 'BSI Index'],
    },
    'handysize': {
        'label': 'Handysize',
        'indices': ['HS1', 'HS2', 'HS3', 'HS4', 'HS5', 'BHSI 38TC', 'BHSI Index'],
    },
}


def indices_redirect(request):
    return redirect('voyage:indices_by_vessel', vessel='capesize')


def indices_dashboard(request, vessel):
    vessel_key = vessel.lower()
    if vessel_key not in VESSEL_INDEX_GROUPS:
        return redirect('voyage:indices_by_vessel', vessel='capesize')

    vessel_config = VESSEL_INDEX_GROUPS[vessel_key]
    all_indices = vessel_config['indices']
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

    if (end_date - start_date).days > 365:
        start_date = end_date - timedelta(days=365)

    selected_indices = request.GET.getlist('indices')
    selected_indices = [index for index in selected_indices if index in all_indices]
    if 'indices' not in request.GET:
        selected_indices = list(all_indices)

    total_days = (end_date - start_date).days + 1
    date_rows = [end_date - timedelta(days=offset) for offset in range(total_days)]
    rows = []
    for date_value in date_rows:
        rows.append(
            {
                'date': date_value,
                'values': {index_name: None for index_name in selected_indices},
            }
        )

    context = {
        'vessel_key': vessel_key,
        'vessel_label': vessel_config['label'],
        'vessel_menu': [
            {'key': key, 'label': config['label']}
            for key, config in VESSEL_INDEX_GROUPS.items()
        ],
        'all_indices': all_indices,
        'selected_indices': selected_indices,
        'start_date': start_date,
        'end_date': end_date,
        'rows': rows,
        'has_data': False,
    }
    return render(request, 'voyage/indices_dashboard.html', context)


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
