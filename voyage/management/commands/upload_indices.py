from datetime import datetime
import os
import sys

import pandas as pd
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Max, Q

from voyage.models import AvailableIndex, DailyIndexValue


class Command(BaseCommand):
    help = 'Upload indices from Excel file to database'

    def add_arguments(self, parser):
        parser.add_argument(
            'file_path',
            type=str,
            help='Path to the Excel file containing indices data',
        )
        parser.add_argument(
            '--vessel-size',
            type=str,
            default='panamax',
            choices=['capesize', 'panamax', 'supramax', 'handysize', 'bunker'],
            help='Vessel size for new indices (default: panamax)',
        )
        parser.add_argument(
            '--sheet-name',
            type=str,
            default=0,
            help='Sheet name or index to read (default: first sheet)',
        )

    def handle(self, *args, **options):
        file_path = options['file_path']
        vessel_size = options['vessel_size']
        sheet_name = options['sheet_name']

        if not os.path.exists(file_path):
            raise CommandError(f'File does not exist: {file_path}')

        try:
            # Read Excel file with pandas
            df = pd.read_excel(file_path, sheet_name=sheet_name, engine='openpyxl')
        except Exception as e:
            raise CommandError(f'Unable to read Excel file: {e}')

        # Clean column names
        df.columns = df.columns.str.strip()

        # Find date column (case-insensitive)
        date_col = None
        for col in df.columns:
            if col.lower() == 'date':
                date_col = col
                break

        if date_col is None:
            raise CommandError('Date column not found in the Excel file.')

        # Convert date column
        df[date_col] = pd.to_datetime(df[date_col], errors='coerce').dt.date
        df = df.dropna(subset=[date_col])

        # Get data columns (exclude date)
        data_columns = [col for col in df.columns if col != date_col and not df[col].isna().all()]

        if not data_columns:
            raise CommandError('No index columns found in the Excel file.')

        with transaction.atomic():
            # Normalize headers and find/create indices
            normalized_headers = {col.lower(): col for col in data_columns}
            existing_query = Q()
            for header in data_columns:
                existing_query |= Q(name__iexact=header)
            existing_indices = AvailableIndex.objects.filter(existing_query) if existing_query else AvailableIndex.objects.none()
            name_to_index = {
                index.name.strip().lower(): index
                for index in existing_indices
            }

            # Create missing indices
            missing_headers = [
                normalized_headers[normalized]
                for normalized in normalized_headers
                if normalized not in name_to_index
            ]

            if missing_headers:
                next_order = AvailableIndex.objects.filter(vessel_size=vessel_size).aggregate(
                    max_order=Max('order')
                )['max_order'] or 0
                new_indices = []
                for header in missing_headers:
                    next_order += 1
                    new_indices.append(
                        AvailableIndex(
                            name=header,
                            vessel_size=vessel_size,
                            order=next_order,
                            is_active=True,
                        )
                    )
                AvailableIndex.objects.bulk_create(new_indices)
                for index in new_indices:
                    name_to_index[index.name.strip().lower()] = index
                self.stdout.write(
                    self.style.SUCCESS(f'Created {len(new_indices)} new indices: {", ".join(missing_headers)}')
                )

            # Process data
            candidate_values = []
            candidate_keys = set()
            ignored_columns = []

            for col in data_columns:
                normalized_name = col.lower()
                index_obj = name_to_index.get(normalized_name)
                if not index_obj:
                    ignored_columns.append(col)
                    continue

                # Filter valid numeric values
                col_data = df[[date_col, col]].dropna()
                col_data = col_data[pd.to_numeric(col_data[col], errors='coerce').notna()]

                for _, row in col_data.iterrows():
                    date_val = row[date_col]
                    value = float(row[col])
                    key = (index_obj.pk, date_val)
                    if key in candidate_keys:
                        continue
                    candidate_keys.add(key)
                    candidate_values.append(
                        DailyIndexValue(
                            index=index_obj,
                            date=date_val,
                            value=value,
                        )
                    )

            # Check existing values
            all_dates = set(df[date_col].dropna())
            all_indices = [name_to_index[col.lower()] for col in data_columns if col.lower() in name_to_index]
            existing_keys = set(
                DailyIndexValue.objects.filter(
                    index__in=all_indices,
                    date__in=all_dates,
                ).values_list('index_id', 'date')
            ) if all_dates and all_indices else set()

            # Filter to create only new values
            values_to_create = []
            for daily_value in candidate_values:
                key = (daily_value.index_id, daily_value.date)
                if key not in existing_keys:
                    values_to_create.append(daily_value)
                    existing_keys.add(key)

            # Bulk create
            DailyIndexValue.objects.bulk_create(values_to_create, ignore_conflicts=True)
            insert_count = len(values_to_create)
            skipped_existing_count = len(candidate_values) - insert_count

            self.stdout.write(
                self.style.SUCCESS(
                    f'Upload completed. Inserted {insert_count} new daily values. '
                    f'Skipped {skipped_existing_count} existing values. '
                    f'Ignored {len(ignored_columns)} unknown columns.'
                )
            )