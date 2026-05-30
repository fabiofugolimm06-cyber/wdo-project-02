# CI local — espelha .github/workflows/ci.yml
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

$env:PYTHONPATH = "."
$env:PYTHONHASHSEED = "42"
$env:WDO_CI = "1"

python -m pip install --upgrade pip
pip install -r requirements.txt

python -m pytest tests/ -v --tb=short

python -m pytest `
    tests/test_ci_determinism_stress.py `
    tests/test_model_v1.py::TestModelPipelineIntegration::test_full_pipeline `
    tests/test_project_determinism.py `
    -v --tb=short
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "CI LOCAL OK"
