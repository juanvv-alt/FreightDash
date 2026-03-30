from datetime import datetime
from io import BytesIO

from django import forms
from django.contrib import admin, messages
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import path, reverse
from openpyxl import load_workbook

from .models import AvailableIndex, CustomIndexPreset, DailyIndexValue, RouteParameters


class IndexUploadForm(forms.Form):
    vessel_size = forms.ChoiceField(
        choices=[
            ('capesize', 'Capesize'),
            ('panamax', 'Panamax'),
            ('supramax', 'Supramax'),
            ('handysize', 'Handysize'),
        ],
        help_text='Assign new index headers to this vessel size if they are not already configured.',
    )
    upload_file = forms.FileField(help_text='Upload preset Excel file (.xlsx) with Date and index columns.')


@admin.register(RouteParameters)
class RouteParametersAdmin(admin.ModelAdmin):
    list_display = ('route', 'intake', 'ballast_distance', 'laden_distance', 'updated_at')
    search_fields = ('route',)
    fieldsets = (
        ('Route Information', {
            'fields': ('route',)
        }),
        ('Distance Parameters', {
            'fields': ('ballast_distance', 'laden_distance'),
        }),
        ('Cargo Parameters', {
            'fields': ('intake', 'load_rate', 'discharge_rate', 'turntime_hours'),
        }),
        ('Port Expenses', {
            'fields': ('port_exp_load_port', 'port_exp_discharge_port'),
        }),
        ('Commission & Margins', {
            'fields': ('freight_commission_pct', 'sea_margin_pct'),
        }),
        ('Speed Parameters', {
            'fields': ('ballast_speed', 'laden_speed'),
        }),
        ('Consumption Parameters', {
            'fields': ('ballast_consumption', 'laden_consumption', 'port_consumption'),
        }),
    )
    readonly_fields = ('created_at', 'updated_at')


@admin.register(CustomIndexPreset)
class CustomIndexPresetAdmin(admin.ModelAdmin):
    list_display = ('name', 'updated_at', 'created_at')
    search_fields = ('name',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(AvailableIndex)
class AvailableIndexAdmin(admin.ModelAdmin):
    list_display = ('name', 'vessel_size', 'order', 'is_active', 'updated_at')
    list_editable = ('order', 'is_active')
    list_filter = ('vessel_size', 'is_active')
    search_fields = ('name',)
    ordering = ('vessel_size', 'order', 'name')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(DailyIndexValue)
class DailyIndexValueAdmin(admin.ModelAdmin):
    list_display = ('date', 'index', 'value', 'updated_at')
    list_filter = ('index__vessel_size', 'index', 'date')
    search_fields = ('index__name',)
    ordering = ('-date', 'index__name')
    readonly_fields = ('created_at', 'updated_at')


def _parse_excel_date(value):
    if isinstance(value, datetime):
        return value.date()
    if hasattr(value, 'year') and hasattr(value, 'month') and hasattr(value, 'day'):
        return value
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return None
        for fmt in ('%Y-%m-%d', '%d-%m-%Y', '%m/%d/%Y', '%d/%m/%Y'):
            try:
                return datetime.strptime(cleaned, fmt).date()
            except ValueError:
                continue
    return None


def upload_indices_view(request):
    if request.method == 'POST':
        form = IndexUploadForm(request.POST, request.FILES)
        if form.is_valid():
            vessel_size = form.cleaned_data['vessel_size']
            upload_file = form.cleaned_data['upload_file']

            try:
                workbook = load_workbook(filename=BytesIO(upload_file.read()), data_only=True)
                sheet = workbook.active
            except Exception:
                messages.error(request, 'Unable to read Excel file. Please upload a valid .xlsx file.')
                return redirect(reverse('admin:indices-upload'))

            header_row_idx = None
            headers = []
            for row_idx, row in enumerate(sheet.iter_rows(min_row=1, max_row=10, values_only=True), start=1):
                cleaned_row = [str(cell).strip() if cell is not None else '' for cell in row]
                if any(cell.lower() == 'date' for cell in cleaned_row):
                    header_row_idx = row_idx
                    headers = cleaned_row
                    break

            if not header_row_idx:
                messages.error(request, 'Header row with a Date column was not found.')
                return redirect(reverse('admin:indices-upload'))

            date_col_idx = None
            for idx, name in enumerate(headers):
                if name.lower() == 'date':
                    date_col_idx = idx
                    break

            if date_col_idx is None:
                messages.error(request, 'Date column is missing in the uploaded file.')
                return redirect(reverse('admin:indices-upload'))

            data_columns = []
            for idx, header in enumerate(headers):
                normalized = header.strip()
                if idx == date_col_idx or not normalized:
                    continue
                data_columns.append((idx, normalized))

            if not data_columns:
                messages.error(request, 'No index columns found in the uploaded file.')
                return redirect(reverse('admin:indices-upload'))

            with transaction.atomic():
                name_to_index = {
                    index.name: index
                    for index in AvailableIndex.objects.filter(name__in=[name for _, name in data_columns])
                }

                created_index_count = 0
                for _, index_name in data_columns:
                    if index_name in name_to_index:
                        continue
                    new_index = AvailableIndex.objects.create(
                        name=index_name,
                        vessel_size=vessel_size,
                        order=100,
                        is_active=True,
                    )
                    name_to_index[index_name] = new_index
                    created_index_count += 1

                upsert_count = 0
                for row in sheet.iter_rows(min_row=header_row_idx + 1, values_only=True):
                    if not row:
                        continue
                    row_date = _parse_excel_date(row[date_col_idx] if len(row) > date_col_idx else None)
                    if not row_date:
                        continue

                    for col_idx, index_name in data_columns:
                        raw_value = row[col_idx] if len(row) > col_idx else None
                        if raw_value in (None, ''):
                            continue
                        try:
                            numeric_value = float(raw_value)
                        except (TypeError, ValueError):
                            continue

                        DailyIndexValue.objects.update_or_create(
                            index=name_to_index[index_name],
                            date=row_date,
                            defaults={'value': numeric_value},
                        )
                        upsert_count += 1

            messages.success(
                request,
                f'Upload completed. Upserted {upsert_count} daily values. '
                f'Created {created_index_count} new available indices.',
            )
            return redirect(reverse('admin:indices-upload'))
    else:
        form = IndexUploadForm()

    context = {
        **admin.site.each_context(request),
        'title': 'Upload Baltic Indices',
        'form': form,
    }
    return render(request, 'admin/indices_upload.html', context)


_voyage_original_get_urls = admin.site.get_urls


def _voyage_admin_urls():
    custom_urls = [
        path(
            'indices-upload/',
            admin.site.admin_view(upload_indices_view),
            name='indices-upload',
        ),
    ]
    return custom_urls + _voyage_original_get_urls()


admin.site.get_urls = _voyage_admin_urls
