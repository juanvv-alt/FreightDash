from collections import defaultdict
from datetime import timedelta

from django.db.models import Max
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone

from voyage.models import DailyIndexValue

from .aggregation import week_over_week
from .analytics import CLASS_INDEX_MAP, generate_signal
from .models import (SNAPSHOT_CLASSES, DailySupplySnapshot, PortCallEvent,
                     SupplySignal, TrackedVessel, VesselState)

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
