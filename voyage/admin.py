from datetime import datetime
from io import BytesIO

from django import forms
from django.contrib import admin, messages
from django.db import transaction
from django.db.models import Q
from django.utils.html import format_html
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


VESSEL_SIZE_CHOICES = [
    ('capesize', 'Capesize'),
    ('panamax', 'Panamax'),
    ('supramax', 'Supramax'),
    ('handysize', 'Handysize'),
]


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
    list_display = ('name', 'vessel_size', 'order', 'is_active', 'updated_at', 'remove_link')
    list_editable = ('order', 'is_active')
    list_filter = ('vessel_size', 'is_active')
    search_fields = ('name',)
    ordering = ('vessel_size', 'order', 'name')
    readonly_fields = ('created_at', 'updated_at')
    actions = ('remove_selected_indices',)

    @admin.action(description='Remove selected indices')
    def remove_selected_indices(self, request, queryset):
        removed = queryset.count()
        queryset.delete()
        self.message_user(request, f'Removed {removed} index record(s).', level=messages.SUCCESS)

    def remove_link(self, obj):
        url = reverse('admin:voyage_availableindex_delete', args=[obj.pk])
        return format_html('<a class="deletelink" href="{}">Remove</a>', url)

    remove_link.short_description = 'Remove'


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

                filtered_data_columns = []
                ignored_columns = []
                for col_idx, index_name in data_columns:
                    if index_name in name_to_index:
                        filtered_data_columns.append((col_idx, index_name))
                    else:
                        ignored_columns.append(index_name)

                if not filtered_data_columns:
                    messages.error(request, 'None of the uploaded index columns exist in Available Indices. Upload aborted.')
                    return redirect(reverse('admin:indices-upload'))

                insert_count = 0
                skipped_existing_count = 0
                for row in sheet.iter_rows(min_row=header_row_idx + 1, values_only=True):
                    if not row:
                        continue
                    row_date = _parse_excel_date(row[date_col_idx] if len(row) > date_col_idx else None)
                    if not row_date:
                        continue

                    for col_idx, index_name in filtered_data_columns:
                        raw_value = row[col_idx] if len(row) > col_idx else None
                        if raw_value in (None, ''):
                            continue
                        try:
                            numeric_value = float(raw_value)
                        except (TypeError, ValueError):
                            continue

                        _, created = DailyIndexValue.objects.get_or_create(
                            index=name_to_index[index_name],
                            date=row_date,
                            defaults={'value': numeric_value},
                        )
                        if created:
                            insert_count += 1
                        else:
                            skipped_existing_count += 1

            messages.success(
                request,
                f'Upload completed. Inserted {insert_count} new daily values. '
                f'Skipped {skipped_existing_count} existing values. '
                f'Ignored {len(ignored_columns)} unknown columns.',
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


def indices_config_view(request):
    if request.method == 'POST':
        with transaction.atomic():
            for index_obj in AvailableIndex.objects.all():
                remove_flag = request.POST.get(f'remove_{index_obj.id}')
                if remove_flag == 'on':
                    index_obj.delete()
                    continue

                new_vessel = request.POST.get(f'vessel_size_{index_obj.id}', index_obj.vessel_size)
                new_order_raw = request.POST.get(f'order_{index_obj.id}', str(index_obj.order))
                new_active = request.POST.get(f'is_active_{index_obj.id}') == 'on'

                if new_vessel not in dict(VESSEL_SIZE_CHOICES):
                    new_vessel = index_obj.vessel_size

                try:
                    new_order = max(0, int(new_order_raw))
                except (TypeError, ValueError):
                    new_order = index_obj.order

                changed = (
                    index_obj.vessel_size != new_vessel
                    or index_obj.order != new_order
                    or index_obj.is_active != new_active
                )
                if changed:
                    index_obj.vessel_size = new_vessel
                    index_obj.order = new_order
                    index_obj.is_active = new_active
                    index_obj.save(update_fields=['vessel_size', 'order', 'is_active', 'updated_at'])

            new_name = (request.POST.get('new_name') or '').strip()
            new_vessel = request.POST.get('new_vessel_size')
            new_order_raw = request.POST.get('new_order', '100')
            new_active = request.POST.get('new_is_active') == 'on'
            if new_name:
                if new_vessel not in dict(VESSEL_SIZE_CHOICES):
                    new_vessel = 'capesize'
                try:
                    new_order = max(0, int(new_order_raw))
                except (TypeError, ValueError):
                    new_order = 100

                AvailableIndex.objects.get_or_create(
                    name=new_name,
                    defaults={
                        'vessel_size': new_vessel,
                        'order': new_order,
                        'is_active': new_active,
                    },
                )

        messages.success(request, 'Indices display configuration updated.')
        return redirect(reverse('admin:indices-config'))

    grouped = {
        'capesize': [],
        'panamax': [],
        'supramax': [],
        'handysize': [],
    }
    for index_obj in AvailableIndex.objects.order_by('vessel_size', 'order', 'name'):
        grouped.setdefault(index_obj.vessel_size, []).append(index_obj)

    context = {
        **admin.site.each_context(request),
        'title': 'Indices Display Config',
        'grouped_indices': grouped,
        'vessel_choices': VESSEL_SIZE_CHOICES,
    }
    return render(request, 'admin/indices_config.html', context)


_voyage_original_get_urls = admin.site.get_urls


def _voyage_admin_urls():
    custom_urls = [
        path(
            'indices-upload/',
            admin.site.admin_view(upload_indices_view),
            name='indices-upload',
        ),
        path(
            'indices-config/',
            admin.site.admin_view(indices_config_view),
            name='indices-config',
        ),
    ]
    return custom_urls + _voyage_original_get_urls()


admin.site.get_urls = _voyage_admin_urls
