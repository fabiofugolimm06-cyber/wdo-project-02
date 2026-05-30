"""
Testes do Paper Trading Engine v1.
"""

from __future__ import annotations

import pandas as pd
import pytest

from microstructure.execution import simulate_execution
from microstructure.papertrading import PaperTradingEngine
from microstructure.risk import risk_filter
from microstructure.strategy_config import get_default_config


class TestPaperTradingBasics:
    def test_initialize_state(self):
        engine = PaperTradingEngine(initial_capital=50_000.0)
        state = engine.initialize_state()
        assert state["position"] == 0
        assert state["entry_price"] is None
        assert state["current_pnl"] == 0.0
        assert state["trades"] == []

    def test_open_and_close_long(self):
        engine = PaperTradingEngine(initial_capital=100_000.0)
        engine.initialize_state()
        engine.update_position(100.0)
        engine.on_signal(1)
        state = engine.get_state()
        assert state["position"] == 1
        assert state["entry_price"] is not None

        engine.update_position(102.0)
        assert engine.get_state()["unrealized_pnl"] > 0

        engine.close_position("manual", price=102.0)
        closed = engine.get_state()
        assert closed["position"] == 0
        assert len(closed["trades"]) == 1
        assert closed["trades"][0]["reason"] == "manual"

    def test_signal_flat_closes(self):
        engine = PaperTradingEngine()
        engine.initialize_state()
        engine.update_position(50.0)
        engine.on_signal(1)
        engine.update_position(51.0)
        engine.on_signal(0)
        assert engine.get_state()["position"] == 0
        assert len(engine.get_state()["trades"]) == 1

    def test_stop_loss_closes(self):
        cfg = get_default_config("paper_sl")
        cfg["parameters"]["backtest"]["stop_loss"] = 0.01
        cfg["parameters"]["backtest"]["take_profit"] = 0.50
        engine = PaperTradingEngine(strategy_config=cfg)
        engine.initialize_state()
        engine.update_position(100.0)
        engine.on_signal(1)
        engine.update_position(98.0)
        state = engine.get_state()
        assert state["position"] == 0
        assert state["trades"][-1]["reason"] == "stop_loss"


class TestRiskAndExecutionIntegration:
    def test_risk_blocks_new_signal(self):
        cfg = get_default_config("paper_risk")
        cfg["parameters"]["backtest"]["stop_loss"] = 0.50
        cfg["parameters"]["backtest"]["take_profit"] = 0.50
        engine = PaperTradingEngine(
            strategy_config=cfg,
            daily_loss_limit=-500.0,
            max_drawdown_limit=-0.05,
        )
        engine.initialize_state()
        engine.update_position(100.0)
        engine.on_signal(1)
        engine.update_position(80.0)
        engine.close_position("manual", price=80.0)
        assert engine.get_state()["realized_pnl"] < 0
        engine.update_position(80.0)
        engine.on_signal(1)
        assert engine.get_state()["position"] == 0
        assert engine.get_state()["trading_enabled"] is False

    def test_execution_alignment(self):
        signals = pd.Series([0, 1, 1, 0])
        filtered = risk_filter(signals, allow_trading=True)
        exec_df, _ = simulate_execution(
            filtered["signals"],
            initial_capital=100_000.0,
            position_size=1.0,
        )
        assert list(exec_df["signal"]) == [0, 1, 1, 0]
        assert exec_df["current_position"].iloc[1] == 1.0


class TestPaperTradingPipeline:
    def test_temporal_sequence(self, capsys):
        engine = PaperTradingEngine(strategy_config=get_default_config("paper_seq"))
        engine.initialize_state()
        prices = [100.0, 100.5, 101.0, 100.0, 99.0]
        signals = [0, 1, 1, -1, 0]

        for px, sig in zip(prices, signals):
            engine.update_position(px)
            engine.on_signal(sig)

        final = engine.get_state()
        assert final["last_price"] == 99.0
        assert len(final["trades"]) >= 1
        assert "current_pnl" in final

        print(f"trades: {len(final['trades'])}, pnl: {final['current_pnl']:.2f}")
        print("PAPER TRADING V1 OK")

        captured = capsys.readouterr()
        assert "PAPER TRADING V1 OK" in captured.out
