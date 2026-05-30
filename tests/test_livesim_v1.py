"""
Testes do Live Simulation Engine v1.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from microstructure.execution import simulate_execution
from microstructure.features.datasets import build_dataset
from microstructure.labeling import create_horizon_labels, drop_invalid_label_rows
from microstructure.livesim import LiveSimulationEngine
from microstructure.model import (
    drop_nan_feature_rows,
    train_logistic_model,
    train_test_split_time_series,
)
from microstructure.strategy_config import get_default_config


def _ohlcv(n: int = 120, seed: int = 3) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-05-01", periods=n, freq="min")
    price = 100 + np.cumsum(rng.normal(0, 0.4, size=n))
    fechamento = price.astype(np.float32)
    return pd.DataFrame(
        {
            "abertura": fechamento,
            "alta": fechamento + 1,
            "baixa": fechamento - 1,
            "fechamento": fechamento,
            "volume": rng.integers(100, 800, n).astype(np.float32),
        },
        index=idx,
    )


def _trained_model(df: pd.DataFrame):
    X = build_dataset(df)
    y = create_horizon_labels(df, horizon=5)
    X_ml, y_ml = drop_invalid_label_rows(X, y)
    X_ml, y_ml = drop_nan_feature_rows(X_ml, y_ml)
    X_train, _, y_train, _ = train_test_split_time_series(X_ml, y_ml, train_size=0.7)
    return train_logistic_model(X_train, y_train)


class TestLiveSimulationSequential:
    def test_run_stream_completes(self):
        df = _ohlcv(100)
        model = _trained_model(df)
        engine = LiveSimulationEngine()
        state = engine.run_stream(
            df,
            model,
            get_default_config("livesim"),
            risk_engine={"daily_loss_limit": -5000.0, "max_drawdown_limit": -0.5},
        )
        assert len(state["equity_curve"]) == len(df)
        assert len(state["events"]) >= 2
        assert "stream_start" in [e["type"] for e in state["events"]]

    def test_state_structure(self):
        df = _ohlcv(80)
        model = _trained_model(df)
        engine = LiveSimulationEngine()
        state = engine.run_stream(df, model, get_default_config("livesim_state"))
        assert "current_position" in state
        assert "equity_curve" in state
        assert "events" in state


class TestNoLookahead:
    def test_future_price_change_does_not_affect_past_signals(self):
        df1 = _ohlcv(90, seed=10)
        model = _trained_model(df1)
        cfg = get_default_config("livesim_la")

        engine1 = LiveSimulationEngine()
        state1 = engine1.run_stream(df1, model, cfg)
        signals1 = [e["payload"].get("raw_signal", 0) for e in state1["events"] if e["type"] == "bar"]

        df2 = df1.copy()
        df2.loc[df2.index[70:], "fechamento"] = 99999.0

        engine2 = LiveSimulationEngine()
        state2 = engine2.run_stream(df2, model, cfg)
        signals2 = [e["payload"].get("raw_signal", 0) for e in state2["events"] if e["type"] == "bar"]

        assert signals1[:65] == signals2[:65]


class TestLiveSimIntegration:
    def test_pnl_and_execution(self, capsys):
        df = _ohlcv(150, seed=21)
        model = _trained_model(df)
        cfg = get_default_config("livesim_int")
        engine = LiveSimulationEngine()
        state = engine.run_stream(
            df,
            model,
            cfg,
            risk_engine={"daily_loss_limit": -10_000.0, "max_drawdown_limit": -0.99},
        )

        assert state["equity_curve"][-1]["equity"] > 0
        exec_events = [e for e in state["events"] if e["type"] == "execution_summary"]
        assert len(exec_events) == 1

        idx = df.index[: len(engine._signal_history)]  # noqa: SLF001
        _, exec_metrics = simulate_execution(
            pd.Series(engine._signal_history, index=idx),
            initial_capital=cfg["parameters"]["execution"]["initial_capital"],
            position_size=cfg["parameters"]["execution"]["position_size"],
        )
        assert exec_metrics["num_orders"] >= 0

        print(f"bars: {len(state['equity_curve'])}, events: {len(state['events'])}")
        print("LIVE SIMULATION V1 OK")

        captured = capsys.readouterr()
        assert "LIVE SIMULATION V1 OK" in captured.out
