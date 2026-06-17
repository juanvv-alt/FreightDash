import csv
import io
from collections import defaultdict
from datetime import date, timedelta

from django.http import HttpResponseNotAllowed, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone

from voyage.models import DailyIndexValue

from .analytics import generate_ob_signal, persist_ob_signal
from .models import (
    SERIES_CHOICES,
    ZONE_CHOICES,
    OBForecastSignal,
    OBTonnageSnapshot,
    OBUploadLog,
)

ZONE_LABELS = dict(ZONE_CHOICES)
SERIES_LABELS = dict(SERIES_CHOICES)
ZONES = [z[0] for z in ZONE_CHOICES]


def _latest_ob_signal(zone, today):
    signal = OBForecastSignal.objects.filter(zone=zone).order_by("-date").first()
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
    result = generate_ob_signal(zone, as_of=today)
    return {
        "direction": result.direction,
        "score": result.score,
        "confidence": result.confidence,
        "method": result.method,
        "drivers": result.drivers,
        "data_days": result.data_days,
        "date": today,
    }


def ob_forecast_view(request):
    today = timezone.localdate()
    cards = []
    for zone_key, zone_label in ZONE_CHOICES:
        signal = _latest_ob_signal(zone_key, today)
        cards.append(
            {
                "zone": zone_key,
                "label": zone_label,
                "signal": signal,
                "confidence_pct": round(signal["confidence"] * 100),
            }
        )

    upload_log = [
        {
            "uploaded_at": log.uploaded_at,
            "zone_label": ZONE_LABELS.get(log.zone, log.zone),
            "series_label": SERIES_LABELS.get(log.series, log.series),
            "rows_added": log.rows_added,
            "rows_skipped": log.rows_skipped,
        }
        for log in OBUploadLog.objects.order_by("-uploaded_at")[:10]
    ]

    context = {
        "cards": cards,
        "zones": ZONE_CHOICES,
        "series_choices": SERIES_CHOICES,
        "upload_log": upload_log,
        "today": today,
    }
    return render(request, "ob_forecast/ob_forecast.html", context)


def ob_chart_data(request, zone):
    if zone not in ZONES:
        return JsonResponse({"error": "Unknown zone"}, status=404)

    today = timezone.localdate()
    start = today - timedelta(days=180)

    rows = (
        OBTonnageSnapshot.objects.filter(zone=zone, date__gte=start)
        .order_by("date", "series")
        .values("date", "series", "vessel_count")
    )

    by_date = defaultdict(dict)
    for row in rows:
        d = row["date"].isoformat()
        by_date[d][row["series"]] = row["vessel_count"]

    labels = sorted(by_date.keys())
    series_out = {
        "BALLAST_AT_SEA": [by_date[d].get("BALLAST_AT_SEA") for d in labels],
        "IN_PORT": [by_date[d].get("IN_PORT") for d in labels],
        "TOTAL": [by_date[d].get("TOTAL") for d in labels],
    }

    idx_qs = (
        DailyIndexValue.objects.filter(index__name="P3A_82", date__gte=start)
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
            "series": series_out,
            "index_name": "P3A_82",
            "index": index_points,
        }
    )


def ob_upload(request):
    if request.method != "POST":
        return redirect("ob_forecast:ob_forecast")

    zone = request.POST.get("zone", "").strip()
    series = request.POST.get("series", "").strip()
    uploaded_file = request.FILES.get("csv_file")

    if not zone or not series or not uploaded_file:
        return redirect("ob_forecast:ob_forecast")

    VALID_ZONES = {z[0] for z in ZONE_CHOICES}
    VALID_SERIES = {s[0] for s in SERIES_CHOICES}
    if zone not in VALID_ZONES or series not in VALID_SERIES:
        return redirect("ob_forecast:ob_forecast")

    text = uploaded_file.read().decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    rows_added = 0
    rows_skipped = 0

    for row in reader:
        try:
            raw_date = row.get("Date", "").strip()
            parsed_date = date.fromisoformat(raw_date[:10])
            vessel_count = int(float(row.get("Vessel Count", 0)))
            vessel_dwt = int(float(row.get("Vessel DWT", 0)))
        except (ValueError, KeyError):
            rows_skipped += 1
            continue

        OBTonnageSnapshot.objects.update_or_create(
            date=parsed_date,
            zone=zone,
            series=series,
            defaults={"vessel_count": vessel_count, "vessel_dwt": vessel_dwt},
        )
        rows_added += 1

    OBUploadLog.objects.create(
        zone=zone,
        series=series,
        filename=uploaded_file.name,
        rows_added=rows_added,
        rows_skipped=rows_skipped,
    )
    return redirect("ob_forecast:ob_forecast")


def ob_daily_entry(request):
    if request.method != "POST":
        return redirect("ob_forecast:ob_forecast")

    raw_date = request.POST.get("entry_date", "").strip()
    try:
        entry_date = date.fromisoformat(raw_date)
    except ValueError:
        return redirect("ob_forecast:ob_forecast")

    for zone_key, _ in ZONE_CHOICES:
        for series_key, _ in SERIES_CHOICES:
            field_name = f"{zone_key}_{series_key}"
            raw_val = request.POST.get(field_name, "").strip()
            if not raw_val:
                continue
            try:
                vessel_count = int(float(raw_val))
            except ValueError:
                continue
            OBTonnageSnapshot.objects.update_or_create(
                date=entry_date,
                zone=zone_key,
                series=series_key,
                defaults={"vessel_count": vessel_count, "vessel_dwt": 0},
            )

    return redirect("ob_forecast:ob_forecast")


def ob_aggregate(request):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    today = timezone.localdate()
    for zone_key, _ in ZONE_CHOICES:
        result = generate_ob_signal(zone_key, as_of=today)
        persist_ob_signal(result, today)

    return redirect("ob_forecast:ob_forecast")
