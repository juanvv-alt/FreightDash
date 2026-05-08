# PDF Indices Upload System

This system allows you to extract freight indices from PDF reports and import them into FreightDash with verification.

## Features

- **PDF Table Extraction**: Automatically detects and extracts index tables from PDF files
- **Data Verification**: Web interface to review extracted data before importing
- **Index Management**: Automatically creates new indices and handles duplicates
- **Daily Automation**: Batch script for scheduled daily uploads

## Installation

1. Install the required dependencies:
```bash
pip install -r requirements.txt
```

The system uses `pdfplumber` for PDF parsing.

## Usage

### Manual Upload

1. **Extract indices from PDF**:
```bash
python manage.py upload_indices_pdf /path/to/report.pdf --vessel-size=panamax --pages=1-3
```

2. **Access verification page**: The command will output a URL like:
   `http://localhost:8000/voyage/verify-pdf-indices/abc123-session-id/`

3. **Review and import**: Use the web interface to select tables and import data.

### Daily Automated Upload

Use the provided batch script for Windows Task Scheduler:

```batch
upload_pdf_indices.bat "C:\Reports\daily_indices.pdf" panamax "1-2"
```

#### Setting up Windows Task Scheduler

1. Open Task Scheduler
2. Create a new task
3. Set trigger to daily at your preferred time
4. Set action to "Start a program"
5. Program: `C:\Users\juan.vanvyve\.vscode\FreightDash\upload_pdf_indices.bat`
6. Arguments: `"C:\Path\To\Your\PDF\report.pdf" panamax "1-2"`
7. Start in: `C:\Users\juan.vanvyve\.vscode\FreightDash`

## Command Options

### upload_indices_pdf command

- `file_path`: Path to PDF file (required)
- `--vessel-size`: Vessel size for indices (default: panamax)
  - Options: capesize, panamax, supramax, handysize, bunker
- `--pages`: Pages to process (default: all)
  - Examples: "1,2,3", "1-5", "all"

### Batch Script Options

```batch
upload_pdf_indices.bat <pdf_path> [vessel_size] [pages]
```

## PDF Format Requirements

The system works best with PDFs containing tabular data with:
- Clear column headers
- Date column (various formats supported)
- Numeric index values
- Consistent table structure

## Troubleshooting

### No Tables Found
- Try specifying specific pages: `--pages=1-3`
- Check if the PDF contains actual tables (not just text/images)
- Ensure tables have clear headers

### Date Parsing Issues
- Supported formats: YYYY-MM-DD, DD/MM/YYYY, MM/DD/YYYY, etc.
- The system tries multiple formats automatically

### Permission Errors
- Ensure the Django application has write access to temp directory
- Check file permissions on the PDF file

## Data Validation

The verification page shows:
- **Extracted tables**: Preview of raw PDF table data
- **Processed data**: Cleaned dates and values
- **Index status**: Whether indices are new or existing
- **Row count**: Number of data points per table

## Security Notes

- Temporary files are stored in system temp directory
- Session data expires when imported or cancelled
- No sensitive data is logged

## Support

If you encounter issues:
1. Check the command output for error messages
2. Verify PDF file is not corrupted
3. Ensure all dependencies are installed
4. Check Django logs for detailed errors