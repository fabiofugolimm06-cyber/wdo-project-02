"""
Testes do Run Management v1.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from microstructure.artifacts import save_pipeline_artifacts
from microstructure.experiments import create_experiment, list_experiments, save_experiment
from microstructure.model_registry import load_registry, register_model, reset_registry, save_registry
from microstructure.run_manager import (
    create_run,
    create_run_directory,
    load_run_metadata,
    save_run_metadata,
)
from microstructure.strategy_config import (
    create_strategy_config,
    flatten_parameters,
    get_default_config,
    load_strategy_config,
)


@pytest.fixture(autouse=True)
def _reset_model_registry():
    reset_registry()
    yield
    reset_registry()


class TestCreateRunDirectory:
    def test_creates_runs_folder(self, tmp_path: Path):
        info = create_run_directory(tmp_path / "runs")
        assert Path(info["run_directory"]).is_dir()
        assert re.match(r"run_\d{8}_\d{6}", info["run_id"])


class TestRunMetadata:
    def test_save_and_load(self, tmp_path: Path):
        cfg = get_default_config("meta_test")
        run_dir = tmp_path / "run_test"
        run_dir.mkdir()
        metadata = {
            "run_id": "run_test",
            "timestamp": "2026-01-01T12:00:00Z",
            "config": cfg,
        }
        save_run_metadata(run_dir, metadata)
        loaded = load_run_metadata(run_dir)
        assert loaded["run_id"] == "run_test"
        assert loaded["config"]["strategy_name"] == "meta_test"


class TestCreateRun:
    def test_full_run_creation(self, tmp_path: Path):
        cfg = create_strategy_config("wdo_run", overrides={"labeling": {"horizon": 7}})
        result = create_run(cfg, base_dir=tmp_path / "runs")

        assert result["run_id"].startswith("run_")
        assert result["timestamp"].endswith("Z")
        run_path = Path(result["run_directory"])
        assert run_path.is_dir()
        assert (run_path / "run_metadata.json").is_file()
        assert (run_path / "strategy_config.json").is_file()

        loaded = load_run_metadata(run_path)
        assert loaded["config"]["parameters"]["labeling"]["horizon"] == 7


class TestRunManagerIntegration:
    def test_strategy_config_artifacts_experiments_registry(
        self, tmp_path: Path, capsys
    ):
        cfg = get_default_config("integrated_run")
        run = create_run(cfg, base_dir=tmp_path / "runs")
        run_dir = Path(run["run_directory"])

        loaded_cfg = load_strategy_config(run_dir)
        flat = flatten_parameters(loaded_cfg)
        report = {
            "total_return": 0.01,
            "annualized_return": 0.02,
            "sharpe": 0.9,
            "max_drawdown": -0.02,
            "calmar_ratio": 1.0,
            "win_rate": 0.5,
            "num_trades": 3,
            "avg_trade_return": 0.001,
            "profit_factor": 1.1,
        }

        save_pipeline_artifacts(
            run_dir,
            {
                "model_metrics": {"accuracy": 0.55},
                "execution_metrics": {"num_orders": 2},
                "backtest_metrics": {"total_return": 0.01},
                "report_metrics": report,
            },
        )
        exp = create_experiment(
            experiment_name=run["run_id"],
            parameters=flat,
            metrics=report,
        )
        save_experiment(run_dir, exp)
        register_model(
            loaded_cfg["strategy_name"],
            "LogisticRegression",
            flat,
            report,
        )
        save_registry(run_dir)

        meta = load_run_metadata(run_dir)
        assert meta["run_id"] == run["run_id"]
        assert len(list_experiments(run_dir)) == 1
        reset_registry()
        assert len(load_registry(run_dir)) == 1

        print(f"run_id: {run['run_id']}, dir: {run_dir.name}")
        print("RUN MANAGER V1 OK")

        captured = capsys.readouterr()
        assert "RUN MANAGER V1 OK" in captured.out
