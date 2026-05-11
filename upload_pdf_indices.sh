#!/usr/bin/env bash
set -euo pipefail

# Daily PDF Indices Upload Script for FreightDash (Linux/macOS)
# Usage: ./upload_pdf_indices.sh /path/to/report.pdf [vessel_size] [pages]

PDF_PATH="$1"
VESSEL_SIZE="${2:-panamax}"
PAGES="${3:-all}"

if [[ -z "$PDF_PATH" ]]; then
  echo "Error: PDF file path is required"
  echo "Usage: $0 /path/to/report.pdf [vessel_size] [pages]"
  echo "Example: $0 /reports/daily_indices.pdf panamax '1-2'"
  exit 1
fi

if [[ ! -f "$PDF_PATH" ]]; then
  echo "Error: PDF file does not exist: $PDF_PATH"
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================"
echo "FreightDash PDF Indices Upload"
echo "========================================"
echo "PDF File: $PDF_PATH"
echo "Vessel Size: $VESSEL_SIZE"
echo "Pages: $PAGES"
echo "========================================"

echo "Running PDF extraction..."
python manage.py upload_indices_pdf "$PDF_PATH" --vessel-size="$VESSEL_SIZE" --pages="$PAGES"

if [[ $? -eq 0 ]]; then
  echo ""
  echo "========================================"
  echo "SUCCESS: PDF indices extracted successfully!"
  echo "========================================"
  echo ""
  echo "Next steps:"
  echo "1. Open your browser and go to the verification URL shown above"
  echo "2. Review the extracted data"
  echo "3. Select tables to import"
  echo "4. Click 'Import Selected Tables'"
  echo ""
else
  echo ""
  echo "========================================"
  echo "ERROR: Failed to extract indices from PDF"
  echo "========================================"
  echo "Check the command output above for details."
  echo ""
  exit 1
fi