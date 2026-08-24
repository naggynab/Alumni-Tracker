param(
    [ValidateSet("full", "country", "city", "district", "field", "employment", "employer", "study_country", "study_institution", "batch", "adoption", "missing_data")]
    [string]$Breakdown = "full"
)

$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot
$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
& $python manage.py export_department_report --breakdown $Breakdown
exit $LASTEXITCODE
