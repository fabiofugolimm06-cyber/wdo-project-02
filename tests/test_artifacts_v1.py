"""
Testes do Artifact Persistence v1.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from microstructure.artifacts import save_pipeline_artifacts
from microstructure.backtest.engine_v3 import run_backtest_v3
from microstructure.features.datasets import build_dataset
from microstructure.pipeline import run_full_pipeline
from microstructure.reporting import generate_performance_report
from microstructure.signal.signal_engine import generate_signals


def _ohlcv(n: int = 350, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=n, freq="min")
    price = 100 + np.cumsum(rng.normal(0, 0.5, size=n))
    fechamento = price.astype(np.float32)
    return pd.DataFrame(
        {
            "abertura": fechamento,
            "alta": fechamento + 1,
            "baixa": fechamento - 1,
            "fechamento": fechamento,
            "volume": rng.integers(100, 1000, n).astype(np.float32),
        },
        index=idx,
    )


_EXPECTED_FILES = {
    "model_metrics.json",
    "execution_metrics.json",
    "backtest_metrics.json",
    "report_metrics.json",
}


class TestSavePipelineArtifacts:
    def test_creates_four_json_files(self, tmp_path: Path):
        payload = {
            "model_metrics": {"accuracy": 0.55, "f1": 0.4},
            "execution_metrics": {"num_orders": 3},
            "backtest_metrics": {"total_return": 0.01},
            "report_metrics": {"calmar_ratio": 1.2},
        }
        out = save_pipeline_artifacts(tmp_path, payload)
        assert len(out["files_saved"]) == 4
        names = {Path(p).name for p in out["files_saved"]}
        assert names == _EXPECTED_FILES

    def test_json_valid_and_reloadable(self, tmp_path: Path):
        payload = {
            "model_metrics": {"precision": 0.6},
            "execution_metrics": {"flat_periods": 10},
            "backtest_metrics": {"sharpe": 0.5},
            "report_metrics": {"profit_factor": 1.5},
        }
        save_pipeline_artifacts(tmp_path, payload)
        for name in _EXPECTED_FILES:
            data = json.loads((tmp_path / name).read_text(encoding="utf-8"))
            assert isinstance(data, dict)

    def test_overwrites_existing(self, tmp_path: Path):
        payload = {
            "model_metrics": {"accuracy": 0.1},
            "execution_metrics": {},
            "backtest_metrics": {},
            "report_metrics": {},
        }
        save_pipeline_artifacts(tmp_path, payload)
        payload["model_metrics"] = {"accuracy": 0.9}
        save_pipeline_artifacts(tmp_path, payload)
        loaded = json.loads((tmp_path / "model_metrics.json").read_text(encoding="utf-8"))
        assert loaded["accuracy"] == pytest.approx(0.9)

    def test_creates_directory_automatically(self, tmp_path: Path):
        nested = tmp_path / "runs" / "2024-01-01"
        save_pipeline_artifacts(
            nested,
            {
                "model_metrics": {},
                "execution_metrics": {},
                "backtest_metrics": {},
                "report_metrics": {},
            },
        )
        assert nested.is_dir()

    def test_invalid_output_dir_raises(self, tmp_path: Path):
        with pytest.raises(ValueError, match="output_dir"):
            save_pipeline_artifacts("", {})
        f = tmp_path / "existing.json"
        f.write_text("{}")
        with pytest.raises(ValueError, match="arquivo"):
            save_pipeline_artifacts(f, {})

    def test_inf_serialized_as_string(self, tmp_path: Path):
        save_pipeline_artifacts(
            tmp_path,
            {
                "model_metrics": {},
                "execution_metrics": {},
                "backtest_metrics": {},
                "report_metrics": {"profit_factor": float("inf")},
            },
        )
        loaded = json.loads((tmp_path / "report_metrics.json").read_text(encoding="utf-8"))
        assert loaded["profit_factor"] == "inf"


class TestArtifactsE2EIntegration:
    def test_pipeline_e2e_and_reporting(self, tmp_path: Path, capsys):
        df = _ohlcv(400)
        pipeline = run_full_pipeline(df, price_col="fechamento")

        sig = generate_signals(build_dataset(df))["signal"]
        bt = run_backtest_v3(df, sig, price_col="fechamento")
        report = generate_performance_report(bt)

        artifact_input = {
            "model_metrics": pipeline["model_metrics"],
            "execution_metrics": pipeline["execution_metrics"],
            "backtest_metrics": pipeline["backtest_metrics"],
            "report_metrics": report,
        }
        out = save_pipeline_artifacts(tmp_path / "e2e_run", artifact_input)

        assert len(out["files_saved"]) == 4
        model_loaded = json.loads(
            (tmp_path / "e2e_run" / "model_metrics.json").read_text(encoding="utf-8")
        )
        assert "accuracy" in model_loaded

        print(f"saved: {len(out['files_saved'])} files")
        print("ARTIFACTS V1 OK")

        captured = capsys.readouterr()
        assert "ARTIFACTS V1 OK" in captured.out
