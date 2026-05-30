"""
Testes do Decision Engine v1 (Decision Core Unification).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import LogisticRegression

from microstructure.backtest.engine_v3 import run_backtest_v3
from microstructure.core import run_decision_pipeline
from microstructure.execution_bridge import ExecutionBridge
from microstructure.features.datasets import build_dataset
from microstructure.labeling import create_horizon_labels, drop_invalid_label_rows
from microstructure.model import (
    drop_nan_feature_rows,
    train_logistic_model,
    train_test_split_time_series,
)
from microstructure.strategy_config import get_default_config


def _ohlcv(n: int = 200, seed: int = 17) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-08-01", periods=n, freq="min")
    price = 100 + np.cumsum(rng.normal(0, 0.4, size=n))
    fechamento = price.astype(np.float32)
    return pd.DataFrame(
        {
            "abertura": fechamento,
            "alta": fechamento + 1,
            "baixa": fechamento - 1,
            "fechamento": fechamento,
            "volume": rng.integers(100, 900, n).astype(np.float32),
        },
        index=idx,
    )


def _dummy_model(df: pd.DataFrame) -> LogisticRegression:
    X = build_dataset(df)
    y = create_horizon_labels(df, horizon=5)
    X_ml, y_ml = drop_invalid_label_rows(X, y)
    X_ml, y_ml = drop_nan_feature_rows(X_ml, y_ml)
    X_train, _, y_train, _ = train_test_split_time_series(X_ml, y_ml, train_size=0.7)
    return train_logistic_model(X_train, y_train)


class TestDecisionModes:
    def test_signal_only(self):
        df = _ohlcv(120)
        out = run_decision_pipeline(df, mode="signal_only")
        assert out["mode"] == "signal_only"
        assert out["model_used"] is False
        assert len(out["signals"]) == len(out["features"])
        assert set(out["signals"].unique()).issubset({-1, 0, 1})

    def test_ml_with_dummy_model(self):
        df = _ohlcv(150)
        model = _dummy_model(df)
        out = run_decision_pipeline(df, mode="ml", model=model, threshold=0.55)
        assert out["model_used"] is True
        assert len(out["signals"]) == len(df)

    def test_hybrid_mode(self):
        df = _ohlcv(150)
        model = _dummy_model(df)
        rule_only = run_decision_pipeline(df, mode="signal_only")["signals"]
        hybrid = run_decision_pipeline(df, mode="hybrid", model=model)["signals"]
        assert len(hybrid) == len(rule_only)
        assert set(hybrid.unique()).issubset({-1, 0, 1})


class TestTemporalConsistency:
    def test_index_aligned_and_monotonic(self):
        df = _ohlcv(100)
        out = run_decision_pipeline(df, mode="signal_only")
        assert out["signals"].index.equals(out["features"].index)
        assert out["timestamp_index"].equals(df.index)

    def test_determinism(self):
        df = _ohlcv(80, seed=99)
        a = run_decision_pipeline(df, mode="signal_only")
        b = run_decision_pipeline(df, mode="signal_only")
        assert a["signals"].equals(b["signals"])


class TestIntegrations:
    def test_backtest_v3_compat(self):
        df = _ohlcv(180)
        out = run_decision_pipeline(df, mode="signal_only")
        sig = out["signals"].reindex(df.index).fillna(0).astype(int)
        bt = run_backtest_v3(df, sig, price_col="fechamento")
        assert "total_return" in bt["metrics"]

    def test_execution_bridge_compat(self):
        df = _ohlcv(60)
        out = run_decision_pipeline(df, mode="signal_only")
        bridge = ExecutionBridge(mode="export")
        price_col = "fechamento"
        for ts in out["signals"].index:
            bridge.process_signal(
                int(out["signals"].loc[ts]),
                float(df.loc[ts, price_col]),
                ts,
            )
        assert len(bridge.get_state()["execution_log"]) == len(out["signals"])


class TestDecisionEnginePipeline:
    def test_full_pipeline(self, capsys):
        df = _ohlcv(200)
        model = _dummy_model(df)
        out = run_decision_pipeline(df, mode="hybrid", model=model)
        assert out["model_used"] is True
        print(f"mode={out['mode']}, signals={out['signals'].value_counts().to_dict()}")
        print("DECISION ENGINE V1 OK")
        captured = capsys.readouterr()
        assert "DECISION ENGINE V1 OK" in captured.out
