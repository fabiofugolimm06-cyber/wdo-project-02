"""
Testes do Strategy Config System v1.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from microstructure.artifacts import save_pipeline_artifacts
from microstructure.experiments import create_experiment, save_experiment
from microstructure.model_registry import (
    load_registry,
    register_model,
    reset_registry,
    save_registry,
)
from microstructure.strategy_config import (
    create_strategy_config,
    flatten_parameters,
    get_default_config,
    load_strategy_config,
    save_strategy_config,
    validate_strategy_config,
)


class TestDefaultConfig:
    def test_default_structure(self):
        cfg = get_default_config("wdo_test")
        validate_strategy_config(cfg)
        assert cfg["config_version"] == "1"
        assert cfg["parameters"]["labeling"]["horizon"] == 5
        assert cfg["parameters"]["model"]["train_size"] == pytest.approx(0.70)

    def test_create_with_overrides(self):
        cfg = create_strategy_config(
            "wdo_custom",
            overrides={"labeling": {"horizon": 10}},
        )
        assert cfg["parameters"]["labeling"]["horizon"] == 10
        assert cfg["parameters"]["model"]["ml_threshold"] == pytest.approx(0.55)


class TestPersistence:
    def test_save_and_load(self, tmp_path: Path):
        cfg = get_default_config("persist_test")
        out = save_strategy_config(tmp_path / "run", cfg)
        loaded = load_strategy_config(out["filepath"])
        assert loaded["config_id"] == cfg["config_id"]
        assert loaded["strategy_name"] == "persist_test"

    def test_load_from_run_dir(self, tmp_path: Path):
        cfg = get_default_config("dir_test")
        save_strategy_config(tmp_path, cfg)
        loaded = load_strategy_config(tmp_path)
        assert loaded["strategy_name"] == "dir_test"

    def test_invalid_config_raises(self):
        with pytest.raises(ValueError):
            validate_strategy_config({"strategy_name": "x"})


class TestFlattenParameters:
    def test_flatten_for_tracking(self):
        cfg = get_default_config("flat")
        flat = flatten_parameters(cfg)
        assert flat["labeling_horizon"] == 5
        assert flat["model_train_size"] == pytest.approx(0.70)
        assert flat["data_price_col"] == "fechamento"


class TestStrategyConfigIntegration:
    def test_with_experiments_registry_artifacts(self, tmp_path: Path, capsys):
        cfg = create_strategy_config(
            "e2e_strategy",
            overrides={"model": {"ml_threshold": 0.60}},
        )
        save_strategy_config(tmp_path, cfg)

        flat = flatten_parameters(cfg)
        report = {
            "total_return": 0.02,
            "sharpe": 1.1,
            "max_drawdown": -0.04,
            "annualized_return": 0.05,
            "calmar_ratio": 1.2,
            "win_rate": 0.5,
            "num_trades": 8,
            "avg_trade_return": 0.001,
            "profit_factor": 1.3,
        }

        save_pipeline_artifacts(
            tmp_path,
            {
                "model_metrics": {"f1": 0.45},
                "execution_metrics": {"num_orders": 4},
                "backtest_metrics": {"total_return": 0.02},
                "report_metrics": report,
            },
        )

        exp = create_experiment(
            experiment_name=cfg["strategy_name"],
            parameters=flat,
            metrics=report,
        )
        save_experiment(tmp_path, exp)

        reset_registry()
        register_model(
            cfg["strategy_name"],
            "LogisticRegression",
            flat,
            report,
        )
        save_registry(tmp_path)

        loaded_cfg = load_strategy_config(tmp_path)
        reset_registry()
        models = load_registry(tmp_path)
        assert loaded_cfg["parameters"]["model"]["ml_threshold"] == pytest.approx(0.60)
        assert len(models) == 1

        print(f"strategy: {loaded_cfg['strategy_name']}, horizon: {loaded_cfg['parameters']['labeling']['horizon']}")
        print("STRATEGY CONFIG V1 OK")

        captured = capsys.readouterr()
        assert "STRATEGY CONFIG V1 OK" in captured.out
