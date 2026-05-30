"""
Testes do Experiment Tracking v1.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from microstructure.artifacts import save_pipeline_artifacts
from microstructure.experiments import (
    create_experiment,
    list_experiments,
    load_experiment,
    save_experiment,
)


def _sample_experiment() -> dict:
    return create_experiment(
        experiment_name="wdo_baseline",
        parameters={"horizon": 5, "train_size": 0.7},
        metrics={"total_return": 0.05, "f1": 0.42},
    )


class TestCreateExperiment:
    def test_structure_and_unique_id(self):
        exp1 = _sample_experiment()
        exp2 = _sample_experiment()
        assert exp1["experiment_id"] != exp2["experiment_id"]
        assert exp1["timestamp"].endswith("Z")
        assert exp1["experiment_name"] == "wdo_baseline"
        assert exp1["parameters"]["horizon"] == 5

    def test_empty_name_raises(self):
        with pytest.raises(ValueError, match="experiment_name"):
            create_experiment("", {}, {})


class TestSaveLoadList:
    def test_save_and_load(self, tmp_path: Path):
        exp = _sample_experiment()
        saved = save_experiment(tmp_path, exp)
        loaded = load_experiment(saved["filepath"])
        assert loaded["experiment_id"] == exp["experiment_id"]
        assert loaded["metrics"]["f1"] == pytest.approx(0.42)

    def test_list_experiments(self, tmp_path: Path):
        save_experiment(tmp_path, _sample_experiment())
        save_experiment(tmp_path, _sample_experiment())
        items = list_experiments(tmp_path)
        assert len(items) == 2
        assert "filepath" in items[0]

    def test_overwrites_same_id(self, tmp_path: Path):
        exp = _sample_experiment()
        save_experiment(tmp_path, exp)
        exp["metrics"] = {"f1": 0.99}
        save_experiment(tmp_path, exp)
        loaded = load_experiment(tmp_path / f"{exp['experiment_id']}.json")
        assert loaded["metrics"]["f1"] == pytest.approx(0.99)

    def test_load_missing_raises(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            load_experiment(tmp_path / "missing.json")


class TestArtifactsCompatibility:
    def test_list_ignores_artifact_metrics_files(self, tmp_path: Path):
        exp = _sample_experiment()
        save_experiment(tmp_path, exp)
        save_pipeline_artifacts(
            tmp_path,
            {
                "model_metrics": {"accuracy": 0.5},
                "execution_metrics": {},
                "backtest_metrics": {},
                "report_metrics": {},
            },
        )
        items = list_experiments(tmp_path)
        assert len(items) == 1
        assert items[0]["experiment_id"] == exp["experiment_id"]


class TestExperimentsIntegration:
    def test_reporting_and_artifacts_flow(self, tmp_path: Path, capsys):
        report = {
            "total_return": 0.02,
            "annualized_return": 0.05,
            "sharpe": 0.8,
            "max_drawdown": -0.03,
            "calmar_ratio": 1.6,
            "win_rate": 0.55,
            "num_trades": 10,
            "avg_trade_return": 0.001,
            "profit_factor": 1.2,
        }
        parameters = {
            "horizon": 5,
            "train_size": 0.7,
            "ml_threshold": 0.55,
        }

        exp = create_experiment(
            experiment_name="e2e_run_001",
            parameters=parameters,
            metrics=report,
        )
        save_experiment(tmp_path / "run_001", exp)
        save_pipeline_artifacts(
            tmp_path / "run_001",
            {
                "model_metrics": {"accuracy": 0.6, "f1": 0.4},
                "execution_metrics": {"num_orders": 5},
                "backtest_metrics": {"total_return": 0.02},
                "report_metrics": report,
            },
        )

        listed = list_experiments(tmp_path / "run_001")
        assert len(listed) == 1
        loaded = load_experiment(listed[0]["filepath"])
        assert loaded["metrics"]["profit_factor"] == pytest.approx(1.2)

        artifact = json.loads(
            (tmp_path / "run_001" / "report_metrics.json").read_text(encoding="utf-8")
        )
        assert artifact["sharpe"] == pytest.approx(0.8)

        print(f"experiments: {len(listed)}")
        print("EXPERIMENT TRACKING V1 OK")

        captured = capsys.readouterr()
        assert "EXPERIMENT TRACKING V1 OK" in captured.out
