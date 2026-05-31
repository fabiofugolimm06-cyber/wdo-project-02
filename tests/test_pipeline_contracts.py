"""
Guardrails de contrato: ML pipeline vs E2E / backtest.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from microstructure.contracts import (
    FORBIDDEN_KEYS_IN_ML_METRICS,
    ML_METRIC_KEYS,
    ML_PIPELINE_RESULT_TOP_KEYS,
    validate_ml_metrics,
    validate_ml_pipeline_result,
)
from microstructure.model.pipeline import run_ml_pipeline_v1
from microstructure.pipeline.end_to_end import run_full_pipeline
from tests.ohlcv_data import make_ohlcv

_ROOT = Path(__file__).resolve().parents[1]
_MODEL_PIPELINE = _ROOT / "microstructure" / "model" / "pipeline.py"
_BACKTEST_PKG = _ROOT / "microstructure" / "backtest"
_REGRESSION_TEST = _ROOT / "tests" / "test_pipeline_regression.py"


def _import_names_from_file(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


class TestMLMetricsSchema:
    def test_run_ml_pipeline_v1_respects_contract(self):
        out = run_ml_pipeline_v1(make_ohlcv(200, seed=42), seed=42)
        validate_ml_pipeline_result(out)
        assert set(out["metrics"].keys()) == ML_METRIC_KEYS

    def test_validate_ml_metrics_rejects_extra_keys(self):
        bad = {k: 0.5 for k in ML_METRIC_KEYS}
        bad["sharpe"] = 1.0
        with pytest.raises(ValueError, match="não permitidas|backtest"):
            validate_ml_metrics(bad)

    def test_validate_ml_metrics_rejects_forbidden_backtest_keys(self):
        with pytest.raises(ValueError, match="backtest|métricas de backtest"):
            validate_ml_metrics({
                "accuracy": 0.5,
                "precision": 0.5,
                "recall": 0.5,
                "f1": 0.5,
                "sharpe": 1.2,
            })

    def test_ml_pipeline_result_rejects_e2e_blocks(self):
        out = run_ml_pipeline_v1(make_ohlcv(80, seed=42), seed=42)
        polluted = dict(out)
        polluted["backtest_metrics"] = {"sharpe": 0.0}
        with pytest.raises(ValueError, match="E2E"):
            validate_ml_pipeline_result(polluted)

    def test_forbidden_keys_documented_include_sharpe(self):
        assert "sharpe" in FORBIDDEN_KEYS_IN_ML_METRICS


class TestE2ESchema:
    def test_run_full_pipeline_has_sharpe_in_backtest_only(self):
        result = run_full_pipeline(make_ohlcv(300, seed=42), price_col="fechamento")
        assert set(result["model_metrics"].keys()) == ML_METRIC_KEYS
        assert "sharpe" in result["backtest_metrics"]
        assert "sharpe" not in result["model_metrics"]


class TestRegressionGuardrails:
    def test_pipeline_regression_does_not_access_sharpe(self):
        text = _REGRESSION_TEST.read_text(encoding="utf-8")
        assert '["sharpe"]' not in text
        assert "['sharpe']" not in text
        assert 'metrics"]["sharpe"' not in text

    def test_pipeline_regression_uses_ml_metric_keys(self):
        text = _REGRESSION_TEST.read_text(encoding="utf-8")
        assert (
            "ML_METRIC_KEYS" in text
            or "accuracy" in text
            or "assert_ml_pipeline_regression_stable" in text
        )


class TestLayerIsolation:
    def test_model_pipeline_does_not_import_backtest(self):
        imports = _import_names_from_file(_MODEL_PIPELINE)
        backtest_imports = {n for n in imports if "backtest" in n}
        assert backtest_imports == set()

    def test_backtest_package_does_not_import_sklearn_metrics(self):
        for py_file in _BACKTEST_PKG.glob("*.py"):
            imports = _import_names_from_file(py_file)
            sklearn_hits = {
                n
                for n in imports
                if n.startswith("sklearn") or "sklearn.metrics" in n
            }
            assert sklearn_hits == set(), f"{py_file.name} importa sklearn: {sklearn_hits}"
