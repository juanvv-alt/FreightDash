import asyncio
import json
import threading
from collections import defaultdict
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.db.models import Max
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone

from voyage.models import DailyIndexValue

from .aggregation import week_over_week
from .analytics import CLASS_INDEX_MAP, CLASS_MARKET_INDEX_MAP, generate_signal
from .models import (SNAPSHOT_CLASSES, DailySupplySnapshot, Port, PortCallEvent,
                     SupplySignal, TrackedVessel, VesselState)

_ingest_lock = threading.Lock()

CLASS_LABELS = {
    "capesize": "Capesize",
    "panamax": "Panamax",
    "supramax": "Supramax",
    "handysize": "Handysize",
}

WOW_FIELDS = [
    ("ballast_at_sea_count", "Ballast at sea"),
    ("laden_at_sea_count", "Laden at sea"),
    ("in_port_load_count", "At load ports"),
    ("in_port_discharge_count", "At discharge ports"),
    ("expected_open_7d", "Expected open (7d)"),
]


def _latest_signal(vessel_class, today):
    """Latest persisted SupplySignal for a class, else compute live."""
    signal = (
        SupplySignal.objects.filter(vessel_class=vessel_class).order_by("-date").first()
    )
    if signal is not None:
        return {
            "direction": signal.direction,
            "score": signal.score,
            "confidence": signal.confidence,
            "method": signal.method,
            "drivers": signal.drivers,
            "data_days": signal.data_days,
            "date": signal.date,
        }
    result = generate_signal(vessel_class, as_of=today)
    return {
        "direction": result.direction,
        "score": result.score,
        "confidence": result.confidence,
        "method": result.method,
        "drivers": result.drivers,
        "data_days": result.data_days,
        "date": today,
    }


def supply_forecast(request):
    today = timezone.localdate()

    cards = []
    for vessel_class in SNAPSHOT_CLASSES:
        signal = _latest_signal(vessel_class, today)
        recent = list(
            DailySupplySnapshot.objects.filter(vessel_class=vessel_class).order_by(
                "-date"
            )[:10]
        )
        latest_snapshot = recent[0] if recent else None
        deltas = []
        if latest_snapshot is not None:
            for field, label in WOW_FIELDS:
                deltas.append(
                    {
                        "label": label,
                        "value": getattr(latest_snapshot, field),
                        "wow": week_over_week(recent, field),
                    }
                )
        cards.append(
            {
                "vessel_class": vessel_class,
                "label": CLASS_LABELS[vessel_class],
                "index_name": CLASS_INDEX_MAP.get(vessel_class),
                "market_index_name": CLASS_MARKET_INDEX_MAP.get(vessel_class),
                "signal": signal,
                "confidence_pct": round(signal["confidence"] * 100),
                "snapshot": latest_snapshot,
                "deltas": deltas,
            }
        )

    events = list(
        PortCallEvent.objects.select_related("vessel", "port").order_by("-timestamp")[
            :30
        ]
    )

    # Data-coverage banner.
    snapshot_dates = (
        DailySupplySnapshot.objects.filter(vessel_class="all")
        .values_list("date", flat=True)
        .order_by("date")
    )
    snapshot_dates = list(snapshot_dates)
    fresh_cutoff = timezone.now() - timedelta(hours=48)
    coverage = {
        "first_date": snapshot_dates[0] if snapshot_dates else None,
        "snapshot_days": len(snapshot_dates),
        "vessels_48h": TrackedVessel.objects.filter(
            last_seen__gte=fresh_cutoff, is_excluded=False
        ).count(),
        "last_heartbeat": VesselState.objects.aggregate(m=Max("updated_at"))["m"],
        "total_vessels": TrackedVessel.objects.count(),
    }

    context = {
        "cards": cards,
        "events": events,
        "coverage": coverage,
        "classes": [(c, CLASS_LABELS[c]) for c in SNAPSHOT_CLASSES],
    }
    return render(request, "supply/supply_forecast.html", context)


def supply_chart_data(request, vessel_class):
    if vessel_class not in SNAPSHOT_CLASSES:
        return JsonResponse({"error": "Unknown vessel class"}, status=404)

    today = timezone.localdate()
    start = today - timedelta(days=180)

    snapshots = (
        DailySupplySnapshot.objects.filter(vessel_class=vessel_class, date__gte=start)
        .order_by("date")
        .values(
            "date",
            "ballast_at_sea_count",
            "laden_at_sea_count",
            "in_port_load_count",
            "in_port_discharge_count",
            "expected_open_7d",
        )
    )
    labels = []
    series = defaultdict(list)
    for row in snapshots:
        labels.append(row["date"].isoformat())
        for key in (
            "ballast_at_sea_count",
            "laden_at_sea_count",
            "in_port_load_count",
            "in_port_discharge_count",
            "expected_open_7d",
        ):
            series[key].append(row[key])

    index_name = CLASS_INDEX_MAP.get(vessel_class)
    index_points = []
    if index_name:
        idx_qs = (
            DailyIndexValue.objects.filter(index__name=index_name, date__gte=start)
            .order_by("date")
            .values_list("date", "value")
        )
        index_points = [
            {"x": d.isoformat(), "y": float(v) if v is not None else None}
            for d, v in idx_qs
        ]

    return JsonResponse(
        {
            "labels": labels,
            "supply": series,
            "index_name": index_name,
            "index": index_points,
        }
    )


def vessel_fleet(request):
    """Summary of all AIS-tracked vessels: positions, class, condition."""
    cutoff_48h = timezone.now() - timedelta(hours=48)

    states = list(
        VesselState.objects.select_related("vessel", "current_port")
        .filter(vessel__is_excluded=False)
        .order_by("vessel__vessel_class", "vessel__name", "vessel__mmsi")
    )

    by_class = defaultdict(int)
    by_condition = defaultdict(int)
    at_sea = 0
    in_port_count = 0

    for s in states:
        by_class[s.vessel.vessel_class] += 1
        by_condition[s.loading_condition] += 1
        if s.current_port_id:
            in_port_count += 1
        else:
            at_sea += 1

    recent_events = list(
        PortCallEvent.objects.select_related("vessel", "port")
        .filter(timestamp__gte=timezone.now() - timedelta(hours=24))
        .order_by("-timestamp")[:20]
    )

    ports = list(Port.objects.filter(is_active=True, basin="pacific").values(
        "id", "name", "latitude", "longitude", "port_type", "radius_nm"
    ))

    vessel_geo = []
    for s in states:
        if s.latitude is not None and s.longitude is not None:
            vessel_geo.append({
                "mmsi": s.vessel.mmsi,
                "name": s.vessel.name or f"MMSI {s.vessel.mmsi}",
                "cls": s.vessel.vessel_class,
                "cond": s.loading_condition,
                "lat": round(s.latitude, 4),
                "lon": round(s.longitude, 4),
                "spd": round(s.speed_knots, 1) if s.speed_knots else None,
                "port": s.current_port.name if s.current_port else None,
                "len": round(s.vessel.length_m) if s.vessel.length_m else None,
            })

    class_breakdown = [
        {"cls": cls, "label": lbl, "count": by_class.get(cls, 0)}
        for cls, lbl in [("capesize", "Capesize"), ("panamax", "Panamax"),
                         ("supramax", "Supramax"), ("handysize", "Handysize")]
    ]

    context = {
        "states": states,
        "total": len(states),
        "class_breakdown": class_breakdown,
        "by_condition": dict(by_condition),
        "at_sea": at_sea,
        "in_port_count": in_port_count,
        "recent_events": recent_events,
        "vessel_geo_json": json.dumps(vessel_geo),
        "ports_json": json.dumps(ports),
        "fresh_count": TrackedVessel.objects.filter(
            last_seen__gte=cutoff_48h, is_excluded=False
        ).count(),
    }
    return render(request, "supply/vessel_fleet.html", context)


def trigger_ingest(request):
    """POST-only: kick off a 5-min AIS ingest in a daemon background thread."""
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    if not getattr(settings, "AISSTREAM_API_KEY", ""):
        return JsonResponse(
            {"error": "AISSTREAM_API_KEY is not set — add it in the Render dashboard under Environment Variables."},
            status=400,
        )

    if cache.get("ais_ingest_running"):
        return JsonResponse(
            {
                "status": "already_running",
                "started_at": cache.get("ais_ingest_started", ""),
            }
        )

    if not _ingest_lock.acquire(blocking=False):
        return JsonResponse({"status": "already_running"})

    def _run():
        try:
            cache.set("ais_ingest_running", True, timeout=400)
            cache.set("ais_ingest_started", timezone.now().isoformat(), timeout=400)
            from .geo import load_port_geos
            from .ingest import AISIngestor

            api_key = getattr(settings, "AISSTREAM_API_KEY", "")
            ingestor = AISIngestor(api_key=api_key, ports=load_port_geos())
            asyncio.run(ingestor.run(duration_seconds=300))
        finally:
            cache.delete("ais_ingest_running")
            cache.set(
                "ais_ingest_last_triggered", timezone.now().isoformat(), timeout=86400
            )
            _ingest_lock.release()

    threading.Thread(target=_run, daemon=True).start()
    return JsonResponse({"status": "started"})


def trigger_aggregate(request):
    """POST-only: run today's supply aggregation in the foreground (fast, <5s)."""
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)
    from .aggregation import build_snapshot
    from .analytics import generate_signal, persist_signal

    today = timezone.localdate()
    build_snapshot(today, basin="pacific")
    for vc in SNAPSHOT_CLASSES:
        result = generate_signal(vc, as_of=today)
        persist_signal(result, today)
    return JsonResponse({"status": "done", "date": today.isoformat()})


def ais_status(request):
    now = timezone.now()
    api_key_set = bool(getattr(settings, "AISSTREAM_API_KEY", ""))
    port_count = Port.objects.filter(is_active=True).count()

    last_heartbeat = VesselState.objects.aggregate(m=Max("updated_at"))["m"]
    heartbeat_age_s = (
        (now - last_heartbeat).total_seconds() if last_heartbeat else None
    )

    total_vessels = TrackedVessel.objects.filter(is_excluded=False).count()
    vessels_24h = TrackedVessel.objects.filter(
        last_seen__gte=now - timedelta(hours=24), is_excluded=False
    ).count()

    events_24h = PortCallEvent.objects.filter(
        timestamp__gte=now - timedelta(hours=24)
    ).count()

    latest_snapshot_date = DailySupplySnapshot.objects.aggregate(m=Max("date"))["m"]
    snapshot_days = DailySupplySnapshot.objects.filter(vessel_class="all").count()

    latest_signal_date = SupplySignal.objects.aggregate(m=Max("date"))["m"]
    latest_signals = (
        list(
            SupplySignal.objects.filter(date=latest_signal_date).order_by(
                "vessel_class"
            )
        )
        if latest_signal_date
        else []
    )

    ingest_running = bool(cache.get("ais_ingest_running"))
    last_triggered = cache.get("ais_ingest_last_triggered")
    last_stats = cache.get("ais_last_stats")
    last_stats_time = cache.get("ais_last_stats_time")

    if not api_key_set:
        overall = "no_key"
    elif last_heartbeat is None:
        overall = "no_data"
    elif heartbeat_age_s is not None and heartbeat_age_s > 7200:
        overall = "stale"
    else:
        overall = "ok"

    if request.GET.get("format") == "json":
        return JsonResponse(
            {
                "overall": overall,
                "ingest_running": ingest_running,
                "last_triggered": last_triggered,
                "total_vessels": total_vessels,
                "vessels_24h": vessels_24h,
                "heartbeat_age_s": heartbeat_age_s,
            }
        )

    context = {
        "api_key_set": api_key_set,
        "port_count": port_count,
        "last_heartbeat": last_heartbeat,
        "heartbeat_age_s": heartbeat_age_s,
        "total_vessels": total_vessels,
        "vessels_24h": vessels_24h,
        "events_24h": events_24h,
        "latest_snapshot_date": latest_snapshot_date,
        "snapshot_days": snapshot_days,
        "latest_signals": latest_signals,
        "overall": overall,
        "ingest_running": ingest_running,
        "last_triggered": last_triggered,
        "last_stats": last_stats,
        "last_stats_time": last_stats_time,
    }
    return render(request, "supply/ais_status.html", context)
