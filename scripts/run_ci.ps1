# CI local — espelha .github/workflows/ci.yml (fast tier)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

$env:PYTHONPATH = "."
$env:PYTHONHASHSEED = "42"
$env:WDO_CI = "1"

python -m pip install --upgrade pip
pip install -r requirements.txt

python scripts/run_architecture_gate.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

python -m pytest -m "not slow and not long" -x --tb=short
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "CI FAST OK"

# Tiers opcionais (manual):
# python -m pytest -m "slow" -x --tb=short
# python -m pytest -m "long" -x --tb=short
