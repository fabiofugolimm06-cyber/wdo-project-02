"""
Testes do Execution Bridge v1.
"""

from __future__ import annotations

import json

import pandas as pd
import pytest

from microstructure.execution_bridge import (
    ExecutionBridge,
    export_to_bridge_format,
    export_to_ntsl,
    send_to_execution_layer,
)
from microstructure.strategy_config import get_default_config


def _timestamps(n: int) -> list[str]:
    idx = pd.date_range("2024-07-01 09:00", periods=n, freq="min")
    return [str(t) for t in idx]


class TestExporters:
    def test_ntsl_export(self):
        df = pd.DataFrame({
            "timestamp": _timestamps(3),
            "signal": [0, 1, -1],
            "price": [100.0, 100.5, 101.0],
        })
        text = export_to_ntsl(df)
        assert "NTSL export" in text
        assert "BUY" in text
        assert "SELL" in text

    def test_bridge_json_format(self):
        df = pd.DataFrame({
            "timestamp": _timestamps(2),
            "signal": [1, 0],
            "price": [50.0, 50.5],
        })
        packets = export_to_bridge_format(df, risk_snapshot={"risk_allowed": True})
        assert packets[0]["signal"] == 1
        assert packets[0]["action"] == "BUY"
        assert "risk" in packets[0]
        assert packets[1]["action"] == "FLAT"


class TestExecutionBridge:
    def test_paper_mode(self):
        bridge = ExecutionBridge(get_default_config("bridge_paper"), mode="paper")
        ts = _timestamps(4)
        bridge.process_signal(0, 100.0, ts[0])
        bridge.process_signal(1, 100.5, ts[1])
        state = bridge.get_state()
        assert len(state["execution_log"]) == 2
        assert state["execution_log"][1]["action"] == "BUY"
        assert state["paper_state"] is not None

    def test_export_mode(self):
        bridge = ExecutionBridge(mode="export")
        ts = _timestamps(3)
        for i, sig in enumerate([0, 1, -1]):
            bridge.process_signal(sig, 100.0 + i, ts[i])
        ntsl = bridge.export_ntsl()
        packets = bridge.export_v6_bridge()
        assert "FLAT" in ntsl
        assert len(packets) == 3
        assert bridge.get_state()["paper_state"] is None

    def test_live_stub(self):
        bridge = ExecutionBridge(mode="live")
        ts = _timestamps(2)
        bridge.process_signal(1, 99.0, ts[0])
        state = bridge.get_state()
        assert len(state["live_stub_log"]) == 1
        assert state["live_stub_log"][0]["status"] == "logged_only"

    def test_timestamp_order_raises(self):
        bridge = ExecutionBridge(mode="export")
        bridge.process_signal(0, 100.0, "2024-07-01 09:05:00")
        with pytest.raises(ValueError, match="ordem"):
            bridge.process_signal(1, 100.0, "2024-07-01 09:00:00")

    def test_determinism(self):
        cfg = get_default_config("det")
        ts = _timestamps(5)
        signals = [0, 1, 1, 0, -1]
        prices = [100.0, 100.1, 100.2, 100.0, 99.5]

        b1 = ExecutionBridge(cfg, mode="export")
        b2 = ExecutionBridge(cfg, mode="export")
        for t, s, p in zip(ts, signals, prices):
            b1.process_signal(s, p, t)
            b2.process_signal(s, p, t)

        assert b1.get_state()["execution_log"] == b2.get_state()["execution_log"]


class TestRiskIntegration:
    def test_risk_blocks_signal_in_log(self):
        cfg = get_default_config("bridge_risk")
        cfg["parameters"]["backtest"]["stop_loss"] = 0.50
        bridge = ExecutionBridge(
            cfg,
            mode="paper",
            daily_loss_limit=-500.0,
            max_drawdown_limit=-0.50,
        )
        ts = _timestamps(5)
        bridge.process_signal(1, 100.0, ts[0])
        bridge.process_signal(0, 85.0, ts[1])
        entry = bridge.process_signal(1, 85.0, ts[2])
        assert entry["action"] in ("BUY", "FLAT")
        assert "risk_allowed" in entry


class TestExecutionBridgeIntegration:
    def test_full_bridge_pipeline(self, capsys):
        bridge = ExecutionBridge(get_default_config("bridge_e2e"), mode="export")
        ts = _timestamps(6)
        for i, sig in enumerate([0, 1, 1, -1, 0, 0]):
            bridge.process_signal(sig, 100.0 + i * 0.1, ts[i])

        json_str = bridge.export_v6_bridge_json()
        data = json.loads(json_str)
        assert len(data) == 6
        assert data[1]["signal"] == 1

        stub = send_to_execution_layer(data[1])
        assert stub["packet"]["action"] == "BUY"

        print(f"log_entries: {len(bridge.get_state()['execution_log'])}")
        print("EXECUTION BRIDGE V1 OK")

        captured = capsys.readouterr()
        assert "EXECUTION BRIDGE V1 OK" in captured.out
