param(
    [Parameter(Mandatory=$true)]
    [string]$PdfPath,

    [string]$VesselSize = "panamax",

    [string]$Pages = "all"
)

# Daily PDF Indices Upload Script for FreightDash
# PowerShell version
#
# Usage: .\upload_pdf_indices.ps1 -PdfPath "C:\Reports\indices_report.pdf" -VesselSize panamax -Pages "1-3"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "FreightDash PDF Indices Upload" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "PDF File: $PdfPath" -ForegroundColor White
Write-Host "Vessel Size: $VesselSize" -ForegroundColor White
Write-Host "Pages: $Pages" -ForegroundColor White
Write-Host "========================================" -ForegroundColor Cyan

# Check if PDF file exists
if (-not (Test-Path $PdfPath)) {
    Write-Host "Error: PDF file does not exist: $PdfPath" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Get the script directory and change to Django project directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

# Run the Django management command
Write-Host "Running PDF extraction..." -ForegroundColor Yellow
try {
    & python manage.py upload_indices_pdf $PdfPath --vessel-size=$VesselSize --pages=$Pages

    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Host "========================================" -ForegroundColor Green
        Write-Host "SUCCESS: PDF indices extracted successfully!" -ForegroundColor Green
        Write-Host "========================================" -ForegroundColor Green
        Write-Host ""
        Write-Host "Next steps:" -ForegroundColor White
        Write-Host "1. Open your browser and go to the verification URL shown above" -ForegroundColor White
        Write-Host "2. Review the extracted data" -ForegroundColor White
        Write-Host "3. Select tables to import" -ForegroundColor White
        Write-Host "4. Click 'Import Selected Tables'" -ForegroundColor White
        Write-Host ""
    } else {
        throw "Command failed with exit code $LASTEXITCODE"
    }
} catch {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Red
    Write-Host "ERROR: Failed to extract indices from PDF" -ForegroundColor Red
    Write-Host "========================================" -ForegroundColor Red
    Write-Host "Error details: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host ""
}

Read-Host "Press Enter to continue"