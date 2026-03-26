from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from .models import RouteParameters
from .forms import TCECalculatorForm
from .calculators import (
    calculate_fuel_and_days,
    calculate_tce,
    calculate_freight_from_tce
)


def tce_calculator(request):
    """
    Main TCE Calculator view.
    Handles route selection and TCE/Freight calculations.
    """
    calculated_tce = None
    calculated_freight = None
    form = TCECalculatorForm(request.POST or None)
    
    # Get all routes for dropdown
    routes = RouteParameters.objects.all()
    
    if request.method == 'POST':
        # Handle route selection (AJAX reload)
        route_id = request.POST.get('route')
        if route_id:
            try:
                route = RouteParameters.objects.get(id=route_id)
                # Populate form with route data
                form.initial = {
                    'route': route_id,
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
            except RouteParameters.DoesNotExist:
                pass
        
        if form.is_valid():
            # Extract form data
            data = form.cleaned_data
            
            # Calculate common data (fuel consumption, voyage days, etc.)
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
            
            # Determine which calculation was requested
            if 'calc_tce' in request.POST:
                # Calculate TCE from freight rate
                calculated_tce = calculate_tce(
                    freight_rate=data['freight_rate'],
                    fuel_price=data['fuel_price'],
                    intake=data['intake'],
                    common_data=common_data
                )
                # Update form to show result
                form.initial['tce_field'] = calculated_tce
            
            elif 'calc_freight' in request.POST:
                # Calculate freight rate from target TCE
                calculated_freight = calculate_freight_from_tce(
                    target_tce=data['tce_field'],
                    fuel_price=data['fuel_price'],
                    intake=data['intake'],
                    common_data=common_data
                )
                # Update form to show result
                form.initial['freight_rate'] = calculated_freight
    
    context = {
        'form': form,
        'routes': routes,
        'calculated_tce': calculated_tce,
        'calculated_freight': calculated_freight,
    }
    
    return render(request, 'voyage/tce_calculator.html', context)
