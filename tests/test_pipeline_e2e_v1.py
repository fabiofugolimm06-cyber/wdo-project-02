"""
Testes do pipeline end-to-end v1.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from microstructure.pipeline import run_full_pipeline


def _ohlcv(n: int = 300, seed: int = 42) -> pd.DataFrame:
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


_MODEL_KEYS = {"accuracy", "precision", "recall", "f1"}
_EXEC_KEYS = {"num_orders", "long_entries", "short_entries", "flat_periods"}
_BT_KEYS = {
    "total_return",
    "sharpe",
    "max_drawdown",
    "win_rate",
    "completed_trades",
}


class TestRunFullPipeline:
    def test_pipeline_runs_without_exception(self):
        df = _ohlcv(300)
        result = run_full_pipeline(df, price_col="fechamento")
        assert result is not None

    def test_all_metric_blocks_present(self):
        df = _ohlcv(350)
        result = run_full_pipeline(df)

        assert "features_shape" in result
        assert len(result["features_shape"]) == 2
        assert result["features_shape"][0] > 0
        assert result["features_shape"][1] > 0

        assert set(result["model_metrics"].keys()) == _MODEL_KEYS
        assert set(result["execution_metrics"].keys()) == _EXEC_KEYS
        assert _BT_KEYS.issubset(result["backtest_metrics"].keys())

    def test_empty_df_raises(self):
        df = _ohlcv(10).iloc[0:0]
        with pytest.raises(ValueError, match="vazio"):
            run_full_pipeline(df)


class TestPipelineE2EIntegration:
    def test_full_end_to_end(self, capsys):
        df = _ohlcv(400)
        result = run_full_pipeline(df, price_col="fechamento")

        assert result["features_shape"][0] > 50
        for k in _MODEL_KEYS:
            assert 0.0 <= result["model_metrics"][k] <= 1.0
        assert result["execution_metrics"]["num_orders"] >= 0
        assert "total_return" in result["backtest_metrics"]

        print(f"features_shape: {result['features_shape']}")
        print(f"model_f1: {result['model_metrics']['f1']:.4f}")
        print(f"backtest_return: {result['backtest_metrics']['total_return']:.4f}")
        print("PIPELINE E2E V1 OK")

        captured = capsys.readouterr()
        assert "PIPELINE E2E V1 OK" in captured.out
