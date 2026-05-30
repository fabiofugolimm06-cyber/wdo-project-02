"""
Testes do Model Registry v1.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from microstructure.artifacts import save_pipeline_artifacts
from microstructure.experiments import create_experiment, list_experiments, save_experiment
from microstructure.model_registry import (
    get_best_model,
    list_models,
    load_registry,
    register_model,
    reset_registry,
    save_registry,
)


@pytest.fixture(autouse=True)
def _clean_registry():
    reset_registry()
    yield
    reset_registry()


def _report_metrics(sharpe: float, total_return: float = 0.01) -> dict:
    return {
        "total_return": total_return,
        "annualized_return": 0.05,
        "sharpe": sharpe,
        "max_drawdown": -0.03,
        "calmar_ratio": 1.0,
        "win_rate": 0.5,
        "num_trades": 5,
        "avg_trade_return": 0.001,
        "profit_factor": 1.1,
    }


class TestRegisterModel:
    def test_register_and_list(self):
        m1 = register_model(
            "wdo_logistic_a",
            "LogisticRegression",
            {"horizon": 5, "train_size": 0.7},
            _report_metrics(0.8),
        )
        m2 = register_model(
            "wdo_logistic_b",
            "LogisticRegression",
            {"horizon": 5, "train_size": 0.8},
            _report_metrics(1.2),
        )
        models = list_models()
        assert len(models) == 2
        assert m1["model_id"] != m2["model_id"]
        assert m1["timestamp"].endswith("Z")


class TestPersistence:
    def test_save_and_load(self, tmp_path: Path):
        register_model("m_a", "LogisticRegression", {"h": 5}, _report_metrics(0.5))
        register_model("m_b", "LogisticRegression", {"h": 5}, _report_metrics(1.5))
        save_registry(tmp_path)

        reset_registry()
        assert list_models() == []

        loaded = load_registry(tmp_path)
        assert len(loaded) == 2
        data = json.loads((tmp_path / "model_registry.json").read_text(encoding="utf-8"))
        assert len(data["models"]) == 2


class TestGetBestModel:
    def test_selects_highest_sharpe(self):
        register_model("low", "LogisticRegression", {}, _report_metrics(0.3))
        register_model("high", "LogisticRegression", {}, _report_metrics(2.1))
        register_model("mid", "LogisticRegression", {}, _report_metrics(1.0))

        best = get_best_model(metric="sharpe")
        assert best["model_name"] == "high"
        assert best["metrics"]["sharpe"] == pytest.approx(2.1)

    def test_empty_registry_raises(self):
        with pytest.raises(ValueError, match="vazio"):
            get_best_model()


class TestIntegration:
    def test_with_experiments_reporting_artifacts(self, tmp_path: Path, capsys):
        report_a = _report_metrics(0.6)
        report_b = _report_metrics(1.4)

        register_model(
            "run_a",
            "LogisticRegression",
            {"ml_threshold": 0.55},
            report_a,
        )
        register_model(
            "run_b",
            "LogisticRegression",
            {"ml_threshold": 0.60},
            report_b,
        )
        save_registry(tmp_path)

        exp = create_experiment(
            "registry_run",
            parameters={"train_size": 0.7},
            metrics=report_b,
        )
        save_experiment(tmp_path, exp)
        save_pipeline_artifacts(
            tmp_path,
            {
                "model_metrics": {"f1": 0.4},
                "execution_metrics": {},
                "backtest_metrics": {},
                "report_metrics": report_b,
            },
        )

        reset_registry()
        load_registry(tmp_path)
        best = get_best_model(metric="sharpe")
        assert best["model_name"] == "run_b"

        assert len(list_experiments(tmp_path)) == 1
        assert (tmp_path / "model_registry.json").is_file()

        print(f"best_model: {best['model_name']}, sharpe: {best['metrics']['sharpe']}")
        print("MODEL REGISTRY V1 OK")

        captured = capsys.readouterr()
        assert "MODEL REGISTRY V1 OK" in captured.out
