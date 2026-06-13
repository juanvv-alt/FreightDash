"""Daily aggregation of vessel state into DailySupplySnapshot rows.

Produces one row per real vessel class plus an 'all' basin row. Counts are
relative inputs to the signal layer, not precise fleet censuses -- terrestrial
AIS undercounts mid-ocean, so at-sea numbers are noisier than in-port numbers.
"""

from datetime import datetime, time, timedelta

from django.utils import timezone

from .geo import PortGeo, nearest_port
from .models import (SNAPSHOT_CLASSES, DailySupplySnapshot, PortCallEvent,
                     VesselState)

OPEN_SPEED_KN = 12.0  # assumed steaming speed for "days to open" proxy


def estimate_days_to_open(lat, lon, discharge_ports, speed_kn=OPEN_SPEED_KN):
    """Rough days until a laden vessel reaches its nearest discharge port.

    A crude proxy for when tonnage comes back open: great-circle distance to the
    closest discharge geofence divided by an assumed steaming speed. Ignores
    routing, congestion, and discharge time on purpose -- v1.
    """
    if not discharge_ports:
        return None
    result = nearest_port(lat, lon, discharge_ports)
    if result is None:
        return None
    _, dist_nm = result
    return dist_nm / (speed_kn * 24.0)


def _discharge_geos(basin):
    from .models import Port

    return [
        PortGeo(p.id, p.name, p.latitude, p.longitude, p.radius_nm, p.port_type)
        for p in Port.objects.filter(
            is_active=True, basin=basin, port_type__in=["discharge", "both"]
        )
    ]


def _port_type_map(basin):
    from .models import Port

    return {p.id: p.port_type for p in Port.objects.filter(is_active=True, basin=basin)}


def build_snapshot(
    target_date, basin="pacific", staleness_hours=48, open_speed_kn=OPEN_SPEED_KN
):
    """Build (and persist) DailySupplySnapshot rows for ``target_date``.

    Returns the list of saved snapshots (the four classes + 'all').
    """
    cutoff = timezone.now() - timedelta(hours=staleness_hours)
    discharge_ports = _discharge_geos(basin)
    port_types = _port_type_map(basin)

    states = list(
        VesselState.objects.filter(
            vessel__last_seen__gte=cutoff,
            vessel__is_excluded=False,
        ).select_related("vessel")
    )

    # Accumulators per class plus 'all'.
    classes = SNAPSHOT_CLASSES + ["all"]
    acc = {
        c: {
            "in_port_load": 0,
            "in_port_discharge": 0,
            "ballast": 0,
            "laden": 0,
            "open_7d": 0,
            "open_14d": 0,
            "total": 0,
            "speed_laden": [],
            "speed_ballast": [],
        }
        for c in classes
    }

    for state in states:
        vclass = state.vessel.vessel_class
        targets = ["all"]
        if vclass in SNAPSHOT_CLASSES:
            targets.append(vclass)

        in_port = state.current_port_id is not None
        ptype = port_types.get(state.current_port_id) if in_port else None
        is_laden = state.loading_condition == "laden"
        is_ballast = state.loading_condition == "ballast"

        days_open = None
        if not in_port and is_laden:
            days_open = estimate_days_to_open(
                state.latitude, state.longitude, discharge_ports, open_speed_kn
            )

        for c in targets:
            bucket = acc[c]
            bucket["total"] += 1
            if in_port:
                # 'both'-type ports count toward discharge (tonnage coming open).
                if ptype == "load":
                    bucket["in_port_load"] += 1
                else:
                    bucket["in_port_discharge"] += 1
                    bucket["open_7d"] += 1
                    bucket["open_14d"] += 1
            else:
                if is_ballast:
                    bucket["ballast"] += 1
                    if state.speed_knots:
                        bucket["speed_ballast"].append(state.speed_knots)
                elif is_laden:
                    bucket["laden"] += 1
                    if state.speed_knots:
                        bucket["speed_laden"].append(state.speed_knots)
                    if days_open is not None and days_open <= 7:
                        bucket["open_7d"] += 1
                    if days_open is not None and days_open <= 14:
                        bucket["open_14d"] += 1

    # Port-call event counts for the 24h window of target_date (local).
    day_start = timezone.make_aware(datetime.combine(target_date, time.min))
    day_end = day_start + timedelta(days=1)
    events = list(
        PortCallEvent.objects.filter(
            timestamp__gte=day_start, timestamp__lt=day_end
        ).select_related("vessel", "port")
    )
    ev_acc = {
        c: {"arr_load": 0, "dep_load": 0, "arr_disch": 0, "dep_disch": 0}
        for c in classes
    }
    for ev in events:
        vclass = ev.vessel.vessel_class
        targets = ["all"]
        if vclass in SNAPSHOT_CLASSES:
            targets.append(vclass)
        is_load = ev.port.port_type == "load"
        for c in targets:
            if ev.event_type == "arrival":
                ev_acc[c]["arr_load" if is_load else "arr_disch"] += 1
            else:
                ev_acc[c]["dep_load" if is_load else "dep_disch"] += 1

    saved = []
    for c in classes:
        b = acc[c]
        e = ev_acc[c]
        snapshot, _ = DailySupplySnapshot.objects.update_or_create(
            date=target_date,
            vessel_class=c,
            basin=basin,
            defaults={
                "in_port_load_count": b["in_port_load"],
                "in_port_discharge_count": b["in_port_discharge"],
                "ballast_at_sea_count": b["ballast"],
                "laden_at_sea_count": b["laden"],
                "expected_open_7d": b["open_7d"],
                "expected_open_14d": b["open_14d"],
                "total_tracked": b["total"],
                "arrivals_load_24h": e["arr_load"],
                "departures_load_24h": e["dep_load"],
                "arrivals_discharge_24h": e["arr_disch"],
                "departures_discharge_24h": e["dep_disch"],
                "avg_speed_laden": (
                    sum(b["speed_laden"]) / len(b["speed_laden"])
                    if b["speed_laden"]
                    else None
                ),
                "avg_speed_ballast": (
                    sum(b["speed_ballast"]) / len(b["speed_ballast"])
                    if b["speed_ballast"]
                    else None
                ),
            },
        )
        saved.append(snapshot)
    return saved


def week_over_week(snapshots, field):
    """Latest value minus the value ~7 days earlier for ``field``; None if absent.

    ``snapshots`` is an iterable of DailySupplySnapshot ordered newest-first.
    """
    rows = list(snapshots)
    if not rows:
        return None
    latest = rows[0]
    target = latest.date - timedelta(days=7)
    prior = min(rows, key=lambda s: abs((s.date - target).days), default=None)
    if prior is None or prior.date == latest.date:
        return None
    return getattr(latest, field) - getattr(prior, field)
