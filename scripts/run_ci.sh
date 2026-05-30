#!/usr/bin/env bash
# CI local — espelha .github/workflows/ci.yml
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

export PYTHONPATH=.
export PYTHONHASHSEED=42
export WDO_CI=1

python -m pip install --upgrade pip
pip install -r requirements.txt

python -m pytest tests/ -v --tb=short

python -m pytest \
  tests/test_ci_determinism_stress.py \
  tests/test_model_v1.py::TestModelPipelineIntegration::test_full_pipeline \
  tests/test_project_determinism.py \
  -v --tb=short
echo "CI LOCAL OK"
