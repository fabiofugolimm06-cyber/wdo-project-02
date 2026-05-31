#!/usr/bin/env bash
# CI local — espelha .github/workflows/ci.yml (fast tier)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

export PYTHONPATH=.
export PYTHONHASHSEED=42
export WDO_CI=1

python -m pip install --upgrade pip
pip install -r requirements.txt

python scripts/run_architecture_gate.py

python -m pytest -m "not slow and not long" -x --tb=short
echo "CI FAST OK"

# Tiers opcionais (manual):
# python -m pytest -m "slow" -x --tb=short
# python -m pytest -m "long" -x --tb=short
