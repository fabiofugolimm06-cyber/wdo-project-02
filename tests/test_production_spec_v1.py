"""
Testes do Production Output Spec v1.
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
from microstructure.execution_bridge.exporters import signal_to_action
from microstructure.production import ProductionSpecV1
from microstructure.strategy_config import get_default_config


def _timestamps(n: int) -> list[str]:
    idx = pd.date_range("2024-08-01 09:00", periods=n, freq="min")
    return [str(t) for t in idx]


class TestExportSignal:
    def test_export_signal_structure(self):
        spec = ProductionSpecV1()
        out = spec.export_signal({
            "timestamp": "2024-08-01 09:00:00",
            "signal": 1,
            "confidence": 0.72,
            "mode": "hybrid",
        })
        assert out["symbol"] == "WDO"
        assert out["signal"] == 1
        assert out["mode"] == "hybrid"
        assert out["confidence"] == pytest.approx(0.72)
        assert out["risk"]["position_size"] > 0
        assert out["risk"]["stop_loss"] > 0
        assert out["risk"]["take_profit"] > 0

    def test_invalid_signal_raises(self):
        spec = ProductionSpecV1()
        with pytest.raises(ValueError, match="sinal"):
            spec.export_signal({"timestamp": "2024-08-01", "signal": 2})


class TestNtslAndBridge:
    def test_ntsl_export(self):
        spec = ProductionSpecV1()
        series = [
            spec.export_signal({"timestamp": _timestamps(3)[i], "signal": s})
            for i, s in enumerate([0, 1, -1])
        ]
        text = spec.to_ntsl(series)
        assert "NTSL export v1" in text
        assert "BUY" in text
        assert "SELL" in text
        assert "total_bars=3" in text

    def test_bridge_json_valid(self):
        spec = ProductionSpecV1(default_mode="ml")
        ts = _timestamps(4)
        series = [
            spec.export_signal({
                "timestamp": ts[i],
                "signal": sig,
                "price": 100.0 + i,
            })
            for i, sig in enumerate([0, 1, -1, 0])
        ]
        raw = spec.to_bridge_json(series)
        data = json.loads(raw)
        assert len(data) == 4
        assert data[1]["action"] == "BUY"
        assert data[2]["signal"] == -1
        assert data[0]["symbol"] == "WDO"
        assert data[1]["risk"]["stop_loss"] > 0


class TestValidateOutput:
    def test_validate_rejects_out_of_order(self):
        spec = ProductionSpecV1()
        records = [
            spec.export_signal({"timestamp": "2024-08-01 09:05:00", "signal": 0}),
            spec.export_signal({"timestamp": "2024-08-01 09:00:00", "signal": 1}),
        ]
        with pytest.raises(ValueError, match="ordem"):
            spec.validate_output(records)

    def test_validate_rejects_bad_risk(self):
        spec = ProductionSpecV1()
        bad = spec.export_signal({
            "timestamp": "2024-08-01 09:00:00",
            "signal": 0,
        })
        bad["risk"]["stop_loss"] = -0.01
        with pytest.raises(ValueError, match="stop_loss"):
            spec.validate_output(bad)


class TestDeterminismAndOrder:
    def test_determinism(self):
        cfg = get_default_config("prod_det")
        spec1 = ProductionSpecV1(strategy_config=cfg)
        spec2 = ProductionSpecV1(strategy_config=cfg)
        ts = _timestamps(5)
        rows = [{"timestamp": t, "signal": s} for t, s in zip(ts, [0, 1, 1, -1, 0])]
        j1 = spec1.to_bridge_json([spec1.export_signal(r) for r in rows])
        j2 = spec2.to_bridge_json([spec2.export_signal(r) for r in rows])
        assert j1 == j2

    def test_temporal_order_in_bridge(self):
        spec = ProductionSpecV1()
        ts = _timestamps(6)
        df = pd.DataFrame({"timestamp": ts, "signal": [0, 1, 0, -1, 0, 1]})
        records = spec.from_dataframe(df, mode="signal")
        parsed = json.loads(spec.to_bridge_json(records))
        stamps = [p["timestamp"] for p in parsed]
        assert stamps == sorted(stamps)


class TestExecutionBridgeCompat:
    def test_same_actions_as_bridge_exporters(self):
        spec = ProductionSpecV1()
        ts = _timestamps(5)
        signals = [0, 1, -1, 0, 1]
        prices = [100.0 + i * 0.1 for i in range(5)]

        bridge_df = pd.DataFrame({
            "timestamp": ts,
            "signal": signals,
            "price": prices,
        })
        bridge_packets = export_to_bridge_format(bridge_df)

        prod_records = [
            spec.export_signal({
                "timestamp": t,
                "signal": s,
                "price": p,
            })
            for t, s, p in zip(ts, signals, prices)
        ]
        prod_packets = json.loads(spec.to_bridge_json(prod_records))

        assert len(prod_packets) == len(bridge_packets)
        for prod, bridge in zip(prod_packets, bridge_packets):
            assert prod["signal"] == bridge["signal"]
            assert prod["action"] == bridge["action"]
            assert prod["action"] == signal_to_action(prod["signal"])

    def test_execution_bridge_pipeline(self):
        cfg = get_default_config("prod_bridge")
        bridge = ExecutionBridge(cfg, mode="export")
        spec = ProductionSpecV1(strategy_config=cfg)
        ts = _timestamps(4)

        for i, sig in enumerate([0, 1, -1, 0]):
            bridge.process_signal(sig, 100.0 + i, ts[i])

        log = bridge.get_state()["execution_log"]
        prod_records = [
            spec.export_signal({
                "timestamp": e["timestamp"],
                "signal": e["signal"],
                "price": e["price"],
                "mode": "signal",
            })
            for e in log
        ]
        prod_json = json.loads(spec.to_bridge_json(prod_records))
        bridge_ntsl = bridge.export_ntsl()
        prod_ntsl = spec.to_ntsl(prod_records)

        assert len(prod_json) == len(log)
        assert "BUY" in prod_ntsl
        assert "BUY" in bridge_ntsl

        stub = send_to_execution_layer({
            "timestamp": prod_json[1]["timestamp"],
            "signal": prod_json[1]["signal"],
            "price": prod_json[1].get("price"),
            "risk": prod_json[1]["risk"],
        })
        assert stub["packet"]["action"] == "BUY"

    def test_ntsl_compatible_with_bridge_exporter(self):
        ts = _timestamps(3)
        df = pd.DataFrame({
            "timestamp": ts,
            "signal": [1, 0, -1],
            "price": [50.0, 50.5, 51.0],
        })
        bridge_text = export_to_ntsl(df)
        spec = ProductionSpecV1()
        prod_text = spec.to_ntsl(spec.from_dataframe(df))
        for action in ("BUY", "SELL", "FLAT"):
            assert action in bridge_text
            assert action in prod_text


class TestProductionSpecPipeline:
    def test_full_pipeline(self, capsys):
        cfg = get_default_config("prod_e2e")
        spec = ProductionSpecV1(strategy_config=cfg)
        ts = _timestamps(6)
        records = [
            spec.export_signal({
                "timestamp": t,
                "signal": s,
                "price": 100.0 + i * 0.05,
                "mode": "hybrid",
                "confidence": 0.9,
            })
            for i, (t, s) in enumerate(zip(ts, [0, 1, 1, -1, 0, 0]))
        ]
        spec.validate_output(records)
        ntsl = spec.to_ntsl(records)
        bridge = spec.to_bridge_json(records)
        assert len(json.loads(bridge)) == 6
        assert "WDO" in ntsl

        print("PRODUCTION SPEC V1 OK")
        captured = capsys.readouterr()
        assert "PRODUCTION SPEC V1 OK" in captured.out
