"""
TCE Calculator helper functions.
Ported from the original PHP implementation.
"""


def calculate_vessel_comparison(global_inputs, voyages, vessels):
    """
    Compare TCE across vessels using the BKI standard breakeven freight.

    global_inputs: {hire, ifo_price, mgo_price, weather_factor}
    voyages: list of dicts {
        name, ballast_dist, laden_dist, load_rate, dis_rate,
        load_factor, dis_factor, turntimes_hours, port_exp, various_exp
    }
    vessels: list of dicts {
        name, intakes (list, one per voyage), laden_speed, ballast_speed,
        laden_cons, ballast_cons, port_cons
    }
    vessels[0] is the BKI standard.

    Returns dict with per-voyage results and weighted average per vessel.
    """
    hire = global_inputs['hire']
    ifo_price = global_inputs['ifo_price']
    mgo_price = global_inputs['mgo_price']
    wf = global_inputs['weather_factor']
    commission_factor = 0.9625  # 3.75% address commission

    voyage_results = []
    vessel_durations = [[0.0] * len(vessels) for _ in voyages]

    for v_idx, voyage in enumerate(voyages):
        vessel_rows = []
        bki_freight = None

        for i, vessel in enumerate(vessels):
            intake = vessel['intakes'][v_idx]
            laden_speed = vessel['laden_speed']
            ballast_speed = vessel['ballast_speed']

            dur_laden = voyage['laden_dist'] / laden_speed / 24 * wf
            dur_ballast = voyage['ballast_dist'] / ballast_speed / 24 * wf
            port_stay = (
                intake / voyage['load_rate'] * voyage['load_factor']
                + intake / voyage['dis_rate'] * voyage['dis_factor']
                + voyage['turntimes_hours'] / 24
            )
            voyage_duration = dur_laden + dur_ballast + port_stay

            hire_cost = voyage_duration * hire * commission_factor
            consumption_mt = (
                dur_laden * vessel['laden_cons']
                + dur_ballast * vessel['ballast_cons']
                + port_stay * vessel['port_cons']
            )
            ifo_cost = consumption_mt * ifo_price
            mgo_cost = voyage_duration * 0.1 * mgo_price
            total_cost = ifo_cost + mgo_cost + voyage['port_exp'] + voyage['various_exp']

            if i == 0:
                # BKI: compute breakeven freight
                bki_freight = (total_cost + hire_cost) / intake if intake > 0 else 0

            freight_nett = bki_freight
            tce = (freight_nett * intake - total_cost) / voyage_duration if voyage_duration > 0 else 0

            vessel_durations[v_idx][i] = voyage_duration
            vessel_rows.append({
                'name': vessel['name'],
                'intake': intake,
                'dur_laden': dur_laden,
                'dur_ballast': dur_ballast,
                'port_stay': port_stay,
                'voyage_duration': voyage_duration,
                'hire_cost': hire_cost,
                'consumption_mt': consumption_mt,
                'ifo_cost': ifo_cost,
                'mgo_cost': mgo_cost,
                'total_cost': total_cost,
                'freight_nett': freight_nett,
                'tce': tce,
            })

        bki_tce = vessel_rows[0]['tce']
        for row in vessel_rows:
            row['pct_vs_bki'] = row['tce'] / bki_tce if bki_tce != 0 else None

        voyage_results.append({
            'name': voyage['name'],
            'bki_freight': bki_freight,
            'bki_tce': bki_tce,
            'vessels': vessel_rows,
        })

    # Weighted average % vs BKI, weighted by voyage duration
    weighted_avgs = []
    for i, vessel in enumerate(vessels):
        total_dur = sum(vessel_durations[v][i] for v in range(len(voyages)))
        if total_dur == 0:
            weighted_avgs.append(None)
            continue
        wa = sum(
            voyage_results[v]['vessels'][i]['pct_vs_bki'] * vessel_durations[v][i]
            for v in range(len(voyages))
            if voyage_results[v]['vessels'][i]['pct_vs_bki'] is not None
        ) / total_dur
        weighted_avgs.append(wa)

    return {
        'voyage_results': voyage_results,
        'weighted_avgs': weighted_avgs,
        'vessels': [v['name'] for v in vessels],
    }


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
