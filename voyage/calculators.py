"""
TCE Calculator helper functions.
Ported from the original PHP implementation.
"""


def calculate_fuel_and_days(
    ballast_distance,
    laden_distance,
    intake,
    load_rate,
    discharge_rate,
    turntime_hours,
    port_exp_load_port,
    port_exp_discharge_port,
    freight_commission_pct,
    sea_margin_pct,
    ballast_speed,
    laden_speed,
    ballast_consumption,
    laden_consumption,
    port_consumption
):
    """
    Calculate fuel consumption, voyage days, and port expenses.
    
    Returns:
        dict: Contains voyage_days, total_fuel_consumed, total_port_expenses, freight_commission
    """
    # Convert percentages to decimals
    freight_commission = freight_commission_pct / 100.0
    sea_margin = sea_margin_pct / 100.0
    
    # FUEL CONSUMPTION
    fuel_consumed_ballast = (
        (ballast_distance / ballast_speed / 24.0)
        * ballast_consumption
        * (1 + sea_margin)
    )
    
    fuel_consumed_laden = (
        (laden_distance / laden_speed / 24.0)
        * laden_consumption
        * (1 + sea_margin)
    )
    
    fuel_consumed_load_port = (
        ((intake / load_rate) + (turntime_hours / 24.0))
        * port_consumption
    )
    
    fuel_consumed_discharge_port = (
        (intake / discharge_rate)
        * port_consumption
    )
    
    total_fuel_consumed = (
        fuel_consumed_ballast
        + fuel_consumed_laden
        + fuel_consumed_load_port
        + fuel_consumed_discharge_port
    )
    
    # PORT EXPENSES
    total_port_expenses = port_exp_load_port + port_exp_discharge_port
    
    # VOYAGE DAYS (with sea margin on the at-sea portions)
    voyage_days = (
        ((ballast_distance / ballast_speed) / 24.0) * (1 + sea_margin)
        + ((laden_distance / laden_speed) / 24.0) * (1 + sea_margin)
        + (turntime_hours / 24.0)
        + (intake / load_rate)
        + (intake / discharge_rate)
    )
    
    return {
        'voyage_days': voyage_days,
        'total_fuel_consumed': total_fuel_consumed,
        'total_port_expenses': total_port_expenses,
        'freight_commission': freight_commission,
    }


def calculate_tce(freight_rate, fuel_price, intake, common_data):
    """
    Calculate TCE (Time Charter Equivalent) from a given freight rate.
    
    Args:
        freight_rate: Freight rate in currency per metric ton
        fuel_price: Fuel price in currency per metric ton
        intake: Cargo intake in metric tons
        common_data: dict from calculate_fuel_and_days
    
    Returns:
        float: TCE in currency per day
    """
    voyage_days = common_data['voyage_days']
    total_fuel_consumed = common_data['total_fuel_consumed']
    total_port_expenses = common_data['total_port_expenses']
    freight_commission = common_data['freight_commission']
    
    # Freight Revenue (minus commission)
    freight_revenue = (freight_rate * intake) * (1 - freight_commission)
    
    # TCE = (Freight Revenue - Port Expenses - Fuel Cost) / Voyage Days
    tce = (
        freight_revenue
        - total_port_expenses
        - (total_fuel_consumed * fuel_price)
    ) / voyage_days
    
    return tce


def calculate_freight_from_tce(target_tce, fuel_price, intake, common_data):
    """
    Calculate the freight rate needed to achieve a target TCE.
    
    Args:
        target_tce: Target TCE in currency per day
        fuel_price: Fuel price in currency per metric ton
        intake: Cargo intake in metric tons
        common_data: dict from calculate_fuel_and_days
    
    Returns:
        float: Freight rate in currency per metric ton
    """
    voyage_days = common_data['voyage_days']
    total_fuel_consumed = common_data['total_fuel_consumed']
    total_port_expenses = common_data['total_port_expenses']
    freight_commission = common_data['freight_commission']
    
    # TCE * days = FreightRevenue - PortExp - Fuel
    # FreightRevenue = FreightRate * intake * (1 - commission)
    # Solving for FreightRate:
    # TCE * days + PortExp + (Fuel * price) = FreightRate * intake * (1 - commission)
    # FreightRate = [ TCE*days + PortExp + Fuel*price ] / [ intake*(1-commission) ]
    
    numerator = (
        (target_tce * voyage_days)
        + total_port_expenses
        + (total_fuel_consumed * fuel_price)
    )
    denominator = intake * (1 - freight_commission)
    
    if denominator == 0:
        return 0
    
    freight_rate = numerator / denominator
    return freight_rate
