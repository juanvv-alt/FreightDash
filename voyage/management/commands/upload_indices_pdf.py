import json
import os
import tempfile
import uuid
from datetime import datetime

import pdfplumber
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from voyage.models import AvailableIndex


class Command(BaseCommand):
    help = 'Extract indices from PDF file and prepare for verification'

    def add_arguments(self, parser):
        parser.add_argument(
            'file_path',
            type=str,
            help='Path to the PDF file containing indices data',
        )
        parser.add_argument(
            '--vessel-size',
            type=str,
            default='panamax',
            choices=['capesize', 'panamax', 'supramax', 'handysize', 'bunker'],
            help='Vessel size for new indices (default: panamax)',
        )
        parser.add_argument(
            '--pages',
            type=str,
            default='all',
            help='Pages to process (e.g., "1,2,3" or "1-5" or "all")',
        )

    def handle(self, *args, **options):
        file_path = options['file_path']
        vessel_size = options['vessel_size']
        pages = options['pages']

        if not os.path.exists(file_path):
            raise CommandError(f'File does not exist: {file_path}')

        # Parse pages argument
        page_numbers = self._parse_pages(pages)

        try:
            with pdfplumber.open(file_path) as pdf:
                if page_numbers == 'all':
                    pages_to_process = pdf.pages
                else:
                    pages_to_process = [pdf.pages[i-1] for i in page_numbers if i-1 < len(pdf.pages)]

                extracted_data = []
                for page_num, page in enumerate(pages_to_process, 1):
                    self.stdout.write(f'Processing page {page_num}...')
                    tables = page.extract_tables()

                    for table_idx, table in enumerate(tables):
                        if not table or len(table) < 2:  # Skip empty or single-row tables
                            continue

                        # Try to identify if this is an indices table
                        processed_table = self._process_table(table, vessel_size)
                        if processed_table:
                            extracted_data.append({
                                'page': page_num,
                                'table_index': table_idx,
                                'data': processed_table,
                                'raw_table': table[:10]  # First 10 rows for preview
                            })

        except Exception as e:
            raise CommandError(f'Unable to process PDF file: {e}')

        if not extracted_data:
            self.stdout.write(
                self.style.WARNING('No suitable index tables found in the PDF.')
            )
            return

        # Create temporary file for verification
        temp_data = {
            'file_path': file_path,
            'vessel_size': vessel_size,
            'extracted_tables': extracted_data,
            'extraction_time': datetime.now().isoformat(),
            'session_id': str(uuid.uuid4())
        }

        # Save to temp file
        temp_dir = os.path.join(tempfile.gettempdir(), 'freightdash_pdf_upload')
        os.makedirs(temp_dir, exist_ok=True)
        temp_file = os.path.join(temp_dir, f'{temp_data["session_id"]}.json')

        with open(temp_file, 'w') as f:
            json.dump(temp_data, f, indent=2, default=str)

        self.stdout.write(
            self.style.SUCCESS(
                f'Extracted {len(extracted_data)} potential index tables from PDF.\n'
                f'Verification session ID: {temp_data["session_id"]}\n'
                f'Access the verification page at: /voyage/verify-pdf-indices/{temp_data["session_id"]}/'
            )
        )

    def _parse_pages(self, pages_str):
        """Parse pages argument into list of page numbers or 'all'."""
        if pages_str.lower() == 'all':
            return 'all'

        pages = []
        for part in pages_str.split(','):
            part = part.strip()
            if '-' in part:
                start, end = part.split('-')
                pages.extend(range(int(start.strip()), int(end.strip()) + 1))
            else:
                pages.append(int(part.strip()))

        return sorted(set(pages))

    def _process_table(self, table, vessel_size):
        """Process a table to extract indices data."""
        if not table or len(table) < 2:
            return None

        # Clean table data
        cleaned_table = []
        for row in table:
            cleaned_row = []
            for cell in row:
                if cell is None:
                    cleaned_row.append('')
                else:
                    cleaned_row.append(str(cell).strip())
            cleaned_table.append(cleaned_row)

        # Find header row (look for 'date' or date-like patterns)
        header_row_idx = None
        headers = []

        for i, row in enumerate(cleaned_table):
            if len(row) < 2:
                continue

            # Check if first column looks like a date
            first_cell = row[0].lower().strip()
            if any(keyword in first_cell for keyword in ['date', 'period', 'month']):
                header_row_idx = i
                headers = row
                break

            # Check if row contains date-like values
            date_like = 0
            for cell in row[:3]:  # Check first few columns
                cell_lower = cell.lower().strip()
                if any(keyword in cell_lower for keyword in ['date', 'period', 'month', 'day']):
                    date_like += 1
            if date_like >= 1:
                header_row_idx = i
                headers = row
                break

        if header_row_idx is None:
            # Assume first row is header
            header_row_idx = 0
            headers = cleaned_table[0]

        # Extract data rows
        data_rows = cleaned_table[header_row_idx + 1:]

        # Clean headers
        headers = [h.strip() for h in headers if h.strip()]

        if len(headers) < 2 or len(data_rows) < 1:
            return None

        # Try to identify date column
        date_col_idx = None
        for i, header in enumerate(headers):
            header_lower = header.lower()
            if any(keyword in header_lower for keyword in ['date', 'period', 'month', 'day']):
                date_col_idx = i
                break

        if date_col_idx is None:
            # Assume first column is date
            date_col_idx = 0

        # Extract index columns (all columns except date)
        index_columns = []
        for i, header in enumerate(headers):
            if i != date_col_idx and header:
                index_columns.append({
                    'name': header,
                    'column_index': i,
                    'existing_index': self._find_existing_index(header, vessel_size)
                })

        if not index_columns:
            return None

        # Process data rows
        processed_data = []
        for row in data_rows:
            if len(row) <= date_col_idx:
                continue

            date_str = row[date_col_idx].strip()
            if not date_str:
                continue

            # Try to parse date
            parsed_date = self._parse_date(date_str)
            if not parsed_date:
                continue

            row_data = {
                'date': parsed_date.isoformat(),
                'original_date': date_str,
                'indices': {}
            }

            for idx_col in index_columns:
                col_idx = idx_col['column_index']
                if col_idx < len(row):
                    value_str = row[col_idx].strip()
                    if value_str:
                        try:
                            value = float(value_str.replace(',', '').replace('$', ''))
                            row_data['indices'][idx_col['name']] = {
                                'value': value,
                                'original_value': value_str
                            }
                        except (ValueError, AttributeError):
                            pass

            if row_data['indices']:
                processed_data.append(row_data)

        if not processed_data:
            return None

        return {
            'headers': headers,
            'date_column': date_col_idx,
            'index_columns': index_columns,
            'data': processed_data,
            'total_rows': len(processed_data)
        }

    def _find_existing_index(self, name, vessel_size):
        """Find existing index by name."""
        try:
            return AvailableIndex.objects.get(
                name__iexact=name.strip(),
                vessel_size=vessel_size
            ).name
        except AvailableIndex.DoesNotExist:
            return None

    def _parse_date(self, date_str):
        """Parse various date formats."""
        date_formats = [
            '%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%d-%m-%Y', '%m-%d-%Y',
            '%b %d, %Y', '%B %d, %Y', '%d %b %Y', '%d %B %Y',
            '%Y/%m/%d', '%Y-%m-%d'
        ]

        for fmt in date_formats:
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue

        # Try to handle some common variations
        date_str = date_str.replace('/', '-').replace('.', '-')

        # Handle month names
        month_names = {
            'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04', 'may': '05', 'jun': '06',
            'jul': '07', 'aug': '08', 'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12',
            'january': '01', 'february': '02', 'march': '03', 'april': '04', 'june': '06',
            'july': '07', 'august': '08', 'september': '09', 'october': '10', 'november': '11', 'december': '12'
        }

        for month_name, month_num in month_names.items():
            if month_name in date_str.lower():
                date_str = date_str.lower().replace(month_name, month_num)

        for fmt in date_formats:
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue

        return None