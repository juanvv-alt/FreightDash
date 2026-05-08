@echo off
REM Daily PDF Indices Upload Script for FreightDash
REM
REM This script extracts indices from a PDF file and prepares them for verification
REM
REM Usage: upload_pdf_indices.bat <pdf_file_path> [vessel_size] [pages]
REM
REM Parameters:
REM   pdf_file_path: Path to the PDF file containing indices
REM   vessel_size: Vessel size (panamax, capesize, etc.) - default: panamax
REM   pages: Pages to process (e.g., "1,2,3" or "1-5") - default: all
REM
REM Example:
REM   upload_pdf_indices.bat "C:\Reports\indices_report.pdf" panamax "1-3"

if "%~1"=="" (
    echo Error: PDF file path is required
    echo Usage: %0 ^<pdf_file_path^> [vessel_size] [pages]
    echo Example: %0 "C:\Reports\indices_report.pdf" panamax "1-3"
    pause
    exit /b 1
)

set PDF_PATH=%~1
set VESSEL_SIZE=%~2
set PAGES=%~3

if "%VESSEL_SIZE%"=="" set VESSEL_SIZE=panamax
if "%PAGES%"=="" set PAGES=all

echo ========================================
echo FreightDash PDF Indices Upload
echo ========================================
echo PDF File: %PDF_PATH%
echo Vessel Size: %VESSEL_SIZE%
echo Pages: %PAGES%
echo ========================================

REM Check if PDF file exists
if not exist "%PDF_PATH%" (
    echo Error: PDF file does not exist: %PDF_PATH%
    pause
    exit /b 1
)

REM Change to the Django project directory
cd /d "%~dp0"

REM Run the Django management command
echo Running PDF extraction...
python manage.py upload_indices_pdf "%PDF_PATH%" --vessel-size=%VESSEL_SIZE% --pages=%PAGES%

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ========================================
    echo SUCCESS: PDF indices extracted successfully!
    echo ========================================
    echo.
    echo Next steps:
    echo 1. Open your browser and go to the verification URL shown above
    echo 2. Review the extracted data
    echo 3. Select tables to import
    echo 4. Click "Import Selected Tables"
    echo.
) else (
    echo.
    echo ========================================
    echo ERROR: Failed to extract indices from PDF
    echo ========================================
    echo Check the error messages above for details.
    echo.
)

echo Press any key to continue...
pause >nul