import csv
import io
from collections import defaultdict
from datetime import date, timedelta

import pandas as pd
from django.contrib import messages
from django.http import HttpResponseNotAllowed, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone

from voyage.models import AvailableIndex, DailyIndexValue

from .analytics import (
    _lag_sweep, _nearest_price, generate_ob_signal,
    load_index, load_panamax_index, load_secondary_index, persist_ob_signal,
    INDEX_NAME, OUTCOME_LAG_DAYS, SECONDARY_INDEX_NAME,
)
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
VALID_ZONES = {z[0] for z in ZONE_CHOICES}
VALID_SERIES = {s[0] for s in SERIES_CHOICES}

SESSION_KEY_INDEX = "ob_selected_index"


def _get_selected_index(request):
    name = request.session.get(SESSION_KEY_INDEX, INDEX_NAME)
    valid = set(
        AvailableIndex.objects.filter(vessel_size="panamax", is_active=True)
        .values_list("name", flat=True)
    )
    return name if name in valid else INDEX_NAME


def ob_set_index(request):
    if request.method != "POST":
        return redirect("ob_forecast:ob_forecast")
    name = request.POST.get("index_name", "").strip()
    valid = set(
        AvailableIndex.objects.filter(vessel_size="panamax", is_active=True)
        .values_list("name", flat=True)
    )
    if name in valid:
        request.session[SESSION_KEY_INDEX] = name
    return redirect("ob_forecast:ob_forecast")


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
    selected_index = _get_selected_index(request)
    panamax_indices = list(
        AvailableIndex.objects.filter(vessel_size="panamax", is_active=True)
        .order_by("order")
        .values_list("name", flat=True)
    )
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
        "selected_index": selected_index,
        "panamax_indices": panamax_indices,
    }
    return render(request, "ob_forecast/ob_forecast.html", context)


def ob_chart_data(request, zone):
    if zone not in ZONES:
        return JsonResponse({"error": "Unknown zone"}, status=404)

    today = timezone.localdate()
    start = today - timedelta(days=180)
    selected_index = _get_selected_index(request)

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
        DailyIndexValue.objects.filter(index__name=selected_index, date__gte=start)
        .order_by("date")
        .values_list("date", "value")
    )
    index_points = [
        {"x": d.isoformat(), "y": float(v) if v is not None else None}
        for d, v in idx_qs
    ]

    sec_series = load_secondary_index()
    sec_points = []
    if not sec_series.empty:
        sec_start = sec_series[sec_series.index >= pd.Timestamp(start)]
        sec_points = [
            {"x": d.date().isoformat(), "y": round(float(v), 2)}
            for d, v in zip(sec_start.index, sec_start.values)
        ]

    return JsonResponse(
        {
            "labels": labels,
            "series": series_out,
            "index_name": selected_index,
            "index": index_points,
            "index2_name": SECONDARY_INDEX_NAME,
            "index2": sec_points,
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
    selected_index = _get_selected_index(request)
    for zone_key, _ in ZONE_CHOICES:
        result = generate_ob_signal(zone_key, as_of=today, index_name=selected_index)
        persist_ob_signal(result, today)

    return redirect("ob_forecast:ob_forecast")


def ob_delete_series(request):
    if request.method != "POST":
        return redirect("ob_forecast:ob_forecast")

    zone = request.POST.get("zone", "").strip()
    series = request.POST.get("series", "").strip()

    if zone not in VALID_ZONES or series not in VALID_SERIES:
        return redirect("ob_forecast:ob_forecast")

    count = OBTonnageSnapshot.objects.filter(zone=zone, series=series).count()

    if request.POST.get("confirmed") == "1":
        OBTonnageSnapshot.objects.filter(zone=zone, series=series).delete()
        OBForecastSignal.objects.filter(zone=zone).delete()
        messages.success(
            request,
            f"Deleted {count} rows for {ZONE_LABELS[zone]} / {SERIES_LABELS[series]}. "
            f"Forecast signals for {ZONE_LABELS[zone]} cleared — run forecast to regenerate.",
        )
        return redirect("ob_forecast:ob_forecast")

    return render(request, "ob_forecast/delete_confirm.html", {
        "zone": zone,
        "zone_label": ZONE_LABELS[zone],
        "series": series,
        "series_label": SERIES_LABELS[series],
        "count": count,
    })


def ob_run_backtest(request, zone):
    if request.method != "POST":
        return redirect("ob_forecast:ob_backtest", zone=zone)
    if zone not in VALID_ZONES:
        return redirect("ob_forecast:ob_forecast")
    selected_index = _get_selected_index(request)
    dates = list(
        OBTonnageSnapshot.objects.filter(zone=zone)
        .values_list("date", flat=True)
        .order_by("date")
        .distinct()
    )
    for d in dates:
        result = generate_ob_signal(zone, as_of=d, index_name=selected_index)
        persist_ob_signal(result, d)
    messages.success(
        request,
        f"Backtest complete — {len(dates)} dates computed for {ZONE_LABELS[zone]}.",
    )
    return redirect("ob_forecast:ob_backtest", zone=zone)


def ob_backtest_view(request, zone):
    if zone not in VALID_ZONES:
        return redirect("ob_forecast:ob_forecast")
    today = timezone.localdate()
    selected_index = _get_selected_index(request)
    signals = list(OBForecastSignal.objects.filter(zone=zone).order_by("date"))
    index_series = load_index(selected_index)
    rows = []
    correct = 0
    total_evaluated = 0
    for sig in signals:
        outcome_date = sig.date + timedelta(days=OUTCOME_LAG_DAYS)
        actual_return = None
        actual_dir = None
        hit = None
        price_start = _nearest_price(index_series, sig.date)
        price_end = _nearest_price(index_series, outcome_date)
        if price_start is not None and price_end is not None:
            actual_return = round((price_end - price_start) / price_start * 100, 2)
            if actual_return > 1.5:
                actual_dir = "bullish"
            elif actual_return < -1.5:
                actual_dir = "bearish"
            else:
                actual_dir = "neutral"
            if actual_dir != "neutral":
                hit = sig.direction == actual_dir
                total_evaluated += 1
                if hit:
                    correct += 1
        rows.append({
            "date": sig.date,
            "direction": sig.direction,
            "score": sig.score,
            "confidence": sig.confidence,
            "method": sig.method,
            "data_days": sig.data_days,
            "actual_return": actual_return,
            "actual_dir": actual_dir,
            "was_correct": hit,
        })
    accuracy_pct = round(correct / total_evaluated * 100, 1) if total_evaluated else None
    lag_sweep = _lag_sweep(signals, index_series)
    context = {
        "zone": zone,
        "zone_label": ZONE_LABELS[zone],
        "zones": ZONE_CHOICES,
        "rows": rows[-60:],
        "total_signals": len(signals),
        "total_evaluated": total_evaluated,
        "accuracy_pct": accuracy_pct,
        "lag_sweep": lag_sweep,
        "today": today,
        "selected_index": selected_index,
    }
    return render(request, "ob_forecast/backtest.html", context)


def ob_backtest_data(request, zone):
    if zone not in VALID_ZONES:
        return JsonResponse({"error": "Unknown zone"}, status=404)
    selected_index = _get_selected_index(request)
    signals = list(OBForecastSignal.objects.filter(zone=zone).order_by("date"))
    index_series = load_index(selected_index)
    labels, signal_scores, confidences, actual_returns, was_correct_list = [], [], [], [], []
    for sig in signals:
        outcome_date = sig.date + timedelta(days=OUTCOME_LAG_DAYS)
        labels.append(sig.date.isoformat())
        signal_scores.append(round(sig.score, 3))
        confidences.append(round(sig.confidence, 3))
        p0 = _nearest_price(index_series, sig.date)
        p1 = _nearest_price(index_series, outcome_date)
        if p0 is not None and p1 is not None:
            ret = round((p1 - p0) / p0 * 100, 2)
            actual_returns.append(ret)
            actual_dir = "bullish" if ret > 1.5 else ("bearish" if ret < -1.5 else "neutral")
            hit = (sig.direction == actual_dir) if actual_dir != "neutral" else None
            was_correct_list.append(hit)
        else:
            actual_returns.append(None)
            was_correct_list.append(None)
    index_points = [
        {"x": d.date().isoformat(), "y": round(float(v), 2)}
        for d, v in zip(index_series.index, index_series.values)
    ]
    correct = sum(1 for x in was_correct_list if x is True)
    evaluated = sum(1 for x in was_correct_list if x is not None)
    lag_sweep = _lag_sweep(signals, index_series)
    return JsonResponse({
        "labels": labels,
        "signal_score": signal_scores,
        "confidence": confidences,
        "actual_return_pct": actual_returns,
        "was_correct": was_correct_list,
        "index": index_points,
        "index_name": selected_index,
        "accuracy_pct": round(correct / evaluated * 100, 1) if evaluated else None,
        "total_signals": len(signals),
        "lag_sweep": lag_sweep,
    })
