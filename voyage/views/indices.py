import csv
from datetime import datetime, timedelta

from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone

from ..models import (
    AvailableIndex,
    CustomIndexPreset,
    DailyIndexValue,
)


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
    'bunker': {
        'label': 'Bunker',
        'indices': [
            'Singapore IFO 380', 'Singapore MGO', 'Singapore VLSFO',
            'Hong Kong IFO 380', 'Hong Kong MGO', 'Hong Kong VLSFO',
            'Rotterdam IFO 380', 'Rotterdam MGO', 'Rotterdam VLSFO',
            'Brent', 'WTI',
        ],
    },
}


def _all_known_indices():
    db_indices = list(
        AvailableIndex.objects.filter(is_active=True)
        .order_by('vessel_size', 'order', 'name')
        .values_list('name', flat=True)
    )
    if db_indices:
        return db_indices

    seen = set()
    ordered = []
    for config in VESSEL_INDEX_GROUPS.values():
        for index_name in config['indices']:
            if index_name in seen:
                continue
            seen.add(index_name)
            ordered.append(index_name)
    return ordered


def _indices_for_vessel(vessel_key):
    db_indices = list(
        AvailableIndex.objects.filter(is_active=True, vessel_size=vessel_key)
        .order_by('order', 'name')
        .values_list('name', flat=True)
    )
    if db_indices:
        return db_indices
    return VESSEL_INDEX_GROUPS[vessel_key]['indices']


def _build_rows(start_date, end_date, selected_indices):
    total_days = (end_date - start_date).days + 1
    date_rows = [
        end_date - timedelta(days=offset)
        for offset in range(total_days)
        if (end_date - timedelta(days=offset)).weekday() < 5
    ]
    values_map = {}

    if selected_indices:
        for value in DailyIndexValue.objects.filter(
            index__name__in=selected_indices,
            date__gte=start_date,
            date__lte=end_date,
            index__is_active=True,
        ).select_related('index'):
            values_map[(value.date, value.index.name)] = value.value

    rows = []
    for date_value in date_rows:
        rows.append(
            {
                'date': date_value,
                'values': {
                    index_name: values_map.get((date_value, index_name))
                    for index_name in selected_indices
                },
            }
        )

    return rows, bool(values_map)


def indices_redirect(request):
    return redirect('voyage:indices_by_vessel', vessel='capesize')


def indices_dashboard(request, vessel):
    vessel_key = vessel.lower()
    if vessel_key not in VESSEL_INDEX_GROUPS:
        return redirect('voyage:indices_by_vessel', vessel='capesize')

    vessel_config = VESSEL_INDEX_GROUPS[vessel_key]
    all_indices = _indices_for_vessel(vessel_key)
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

    selected_indices_raw = request.GET.getlist('indices')
    if 'indices' not in request.GET:
        selected_indices = list(all_indices)
    else:
        selected_indices = []
        seen_indices = set()
        for index_name in selected_indices_raw:
            cleaned = index_name.strip()
            if not cleaned or len(cleaned) > 80:
                continue
            if cleaned in seen_indices:
                continue
            seen_indices.add(cleaned)
            selected_indices.append(cleaned)

    rows, has_data = _build_rows(start_date, end_date, selected_indices)

    # CSV download
    if request.GET.get('download') == '1' and selected_indices:
        response = HttpResponse(content_type='text/csv')
        safe_vessel = vessel_key.replace('/', '_')
        response['Content-Disposition'] = (
            f'attachment; filename="{safe_vessel}_indices_{start_date}_{end_date}.csv"'
        )
        writer = csv.writer(response)
        writer.writerow(['Date'] + selected_indices)
        for row in rows:
            writer.writerow(
                [row['date'].strftime('%Y-%m-%d')]
                + [row['values'].get(idx) if row['values'].get(idx) is not None else '' for idx in selected_indices]
            )
        return response

    section_label = 'Bunkers' if vessel_key == 'bunker' else 'Indices'

    context = {
        'vessel_key': vessel_key,
        'vessel_label': vessel_config['label'],
        'vessel_menu': [
            {'key': key, 'label': config['label']}
            for key, config in VESSEL_INDEX_GROUPS.items()
            if key != 'bunker'
        ],
        'all_indices': all_indices,
        'selected_indices': selected_indices,
        'start_date': start_date,
        'end_date': end_date,
        'rows': rows,
        'has_data': has_data,
        'section_label': section_label,
    }
    return render(request, 'voyage/indices_dashboard.html', context)


def indices_chart_data(request, vessel):
    from collections import defaultdict
    vessel_key = vessel.lower()
    if vessel_key not in VESSEL_INDEX_GROUPS:
        return JsonResponse({'error': 'Unknown vessel'}, status=404)

    today = timezone.localdate()
    default_start = today - timedelta(days=365)

    try:
        start_date = datetime.strptime(request.GET.get('start', default_start.isoformat()), '%Y-%m-%d').date()
    except ValueError:
        start_date = default_start

    try:
        end_date = datetime.strptime(request.GET.get('end', today.isoformat()), '%Y-%m-%d').date()
    except ValueError:
        end_date = today

    if start_date > end_date:
        start_date, end_date = end_date, start_date

    indices_param = request.GET.get('indices', '')
    requested = [i.strip() for i in indices_param.split(',') if i.strip()] if indices_param else []

    all_vessel_indices = _indices_for_vessel(vessel_key)
    allowed = set(all_vessel_indices)
    selected = [i for i in requested if i in allowed] if requested else list(all_vessel_indices)

    if not selected:
        return JsonResponse({'traces': [], 'indices': []})

    qs = (
        DailyIndexValue.objects
        .filter(index__name__in=selected, index__is_active=True, date__gte=start_date, date__lte=end_date)
        .select_related('index')
        .order_by('index__name', 'date')
        .values_list('index__name', 'date', 'value')
    )

    buckets = defaultdict(lambda: {'x': [], 'y': []})
    for index_name, date_val, value in qs:
        buckets[index_name]['x'].append(date_val.isoformat())
        buckets[index_name]['y'].append(float(value) if value is not None else None)

    traces = [
        {'name': name, 'x': buckets[name]['x'], 'y': buckets[name]['y']}
        for name in selected if name in buckets
    ]
    return JsonResponse({'traces': traces, 'indices': selected})


def indices_custom(request):
    all_indices = _all_known_indices()

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'save_preset':
            preset_name = (request.POST.get('preset_name') or '').strip()
            selected_raw = request.POST.getlist('indices')
            selected_indices = []
            seen = set()
            for index_name in selected_raw:
                cleaned = index_name.strip()
                if not cleaned or len(cleaned) > 80 or cleaned in seen:
                    continue
                seen.add(cleaned)
                selected_indices.append(cleaned)

            if preset_name and selected_indices:
                CustomIndexPreset.objects.update_or_create(
                    name=preset_name,
                    defaults={'indices': selected_indices},
                )

        if action == 'delete_preset':
            preset_id = request.POST.get('preset_id')
            try:
                CustomIndexPreset.objects.filter(id=int(preset_id)).delete()
            except (TypeError, ValueError):
                pass

        return redirect('voyage:indices_custom')

    presets = list(CustomIndexPreset.objects.all())
    selected_preset_id_raw = request.GET.get('preset')
    selected_preset = None
    if selected_preset_id_raw:
        try:
            selected_preset = CustomIndexPreset.objects.filter(id=int(selected_preset_id_raw)).first()
        except ValueError:
            selected_preset = None

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

    selected_indices_raw = request.GET.getlist('indices')
    selected_indices = []
    seen = set()
    for index_name in selected_indices_raw:
        cleaned = index_name.strip()
        if not cleaned or len(cleaned) > 80 or cleaned in seen:
            continue
        seen.add(cleaned)
        selected_indices.append(cleaned)

    if not selected_indices and selected_preset:
        selected_indices = selected_preset.indices
    if not selected_indices:
        selected_indices = all_indices[:8]

    rows, has_data = _build_rows(start_date, end_date, selected_indices)

    context = {
        'all_indices': all_indices,
        'selected_indices': selected_indices,
        'start_date': start_date,
        'end_date': end_date,
        'rows': rows,
        'has_data': has_data,
        'presets': presets,
        'selected_preset_id': selected_preset.id if selected_preset else None,
        'selected_preset_name': selected_preset.name if selected_preset else '',
    }
    return render(request, 'voyage/indices_custom.html', context)
