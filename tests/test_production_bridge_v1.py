"""
Testes da Production Bridge Layer v1.
"""

from __future__ import annotations

import json

import pandas as pd
import pytest

from microstructure.execution_bridge import export_to_bridge_format, export_to_ntsl
from microstructure.execution_bridge.exporters import signal_to_action
from microstructure.production import (
    build_production_packet,
    build_production_packets_ordered,
    validate_production_packet,
)


def _meta(ts: str, signal: int = 1, price: float = 100.0) -> dict:
    return {
        "timestamp": ts,
        "price": price,
        "risk": {
            "position_size": 1.0,
            "stop_loss": 0.01,
            "take_profit": 0.02,
        },
    }


class TestBuildProductionPacket:
    def test_required_structure_ntsl(self):
        pkt = build_production_packet(1, _meta("2024-12-01 09:00:00"), mode="ntsl")
        validate_production_packet(pkt)
        assert pkt["symbol"] == "WDO"
        assert pkt["signal"] == 1
        assert pkt["mode"] == "ntsl"
        assert "NTSL" in pkt["execution"]["ntsl"]
        assert "BUY" in pkt["execution"]["ntsl"]
        assert pkt["execution"]["bridge_json"] is None
        assert pkt["execution"]["api_payload"] is None

    def test_bridge_json_valid(self):
        pkt = build_production_packet(-1, _meta("2024-12-01 09:05:00"), mode="bridge")
        validate_production_packet(pkt)
        bridge = pkt["execution"]["bridge_json"]
        assert bridge["signal"] == -1
        assert bridge["action"] == "SELL"
        assert bridge["risk"]["stop_loss"] > 0
        json.dumps(bridge)

    def test_api_stub(self):
        pkt = build_production_packet(0, _meta("2024-12-01 09:10:00"), mode="api")
        api = pkt["execution"]["api_payload"]
        assert api["status"] == "not_implemented"
        assert api["body"]["signal"] == 0
        assert api["body"]["side"] == "FLAT"


class TestModeConsistency:
    def test_same_core_fields_across_modes(self):
        meta = _meta("2024-12-01 10:00:00", price=101.5)
        base = {"signal": 1, **meta}
        ntsl = build_production_packet(1, meta, mode="ntsl")
        bridge = build_production_packet(1, meta, mode="bridge")
        api = build_production_packet(1, meta, mode="api")

        for pkt in (ntsl, bridge, api):
            assert pkt["timestamp"] == base["timestamp"] or pkt["timestamp"] == meta["timestamp"]
            assert pkt["symbol"] == "WDO"
            assert pkt["signal"] == 1
            assert pkt["risk"] == ntsl["risk"]

        assert bridge["execution"]["bridge_json"]["action"] == signal_to_action(1)


class TestDeterminism:
    def test_deterministic_output(self):
        meta = _meta("2024-12-01 11:00:00")
        a = build_production_packet(1, meta, mode="bridge")
        b = build_production_packet(1, meta, mode="bridge")
        assert a == b


class TestTemporalOrdering:
    def test_ordered_packets(self):
        items = [
            (1, _meta("2024-12-01 09:02:00")),
            (0, _meta("2024-12-01 09:00:00")),
            (-1, _meta("2024-12-01 09:01:00")),
        ]
        packets = build_production_packets_ordered(items, mode="bridge")
        stamps = [p["timestamp"] for p in packets]
        assert stamps == sorted(stamps)


class TestExecutionBridgeCompat:
    def test_bridge_matches_exporter(self):
        ts = "2024-12-01 09:15:00"
        df = pd.DataFrame({
            "timestamp": [ts],
            "signal": [1],
            "price": [5450.0],
        })
        bridge_ref = export_to_bridge_format(df, risk_snapshot={"risk_allowed": True})[0]

        pkt = build_production_packet(
            1,
            {
                "timestamp": ts,
                "price": 5450.0,
                "risk": bridge_ref["risk"],
                "include_symbol": False,
            },
            mode="bridge",
        )
        prod = pkt["execution"]["bridge_json"]
        assert prod["signal"] == bridge_ref["signal"]
        assert prod["action"] == bridge_ref["action"]
        assert prod["price"] == bridge_ref["price"]

    def test_ntsl_compatible_with_exporter(self):
        ts = "2024-12-01 09:20:00"
        df = pd.DataFrame({
            "timestamp": [ts],
            "signal": [1],
            "price": [100.0],
        })
        ref = export_to_ntsl(df)
        pkt = build_production_packet(1, _meta(ts), mode="ntsl")
        assert "BUY" in ref
        assert "BUY" in pkt["execution"]["ntsl"]


class TestValidation:
    def test_invalid_signal_raises(self):
        with pytest.raises(ValueError, match="sinal"):
            build_production_packet(2, _meta("2024-12-01"))

    def test_missing_timestamp_raises(self):
        with pytest.raises(ValueError, match="timestamp"):
            build_production_packet(0, {"price": 1.0})


class TestProductionBridgePipeline:
    def test_full_pipeline(self, capsys):
        for mode in ("ntsl", "bridge", "api"):
            pkt = build_production_packet(1, _meta("2024-12-01 12:00:00"), mode=mode)
            validate_production_packet(pkt)

        print("PRODUCTION BRIDGE V1 OK")
        captured = capsys.readouterr()
        assert "PRODUCTION BRIDGE V1 OK" in captured.out
