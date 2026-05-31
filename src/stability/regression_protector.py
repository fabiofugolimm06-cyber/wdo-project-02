"""
regression_protector.py — proteção de baseline contra drift comportamental.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def _canonical_gate_slice(gate_reports: dict[str, dict[str, Any]]) -> str:
    slim = {
        gate: {
            "status": report.get("status"),
            "failures": sorted(report.get("failures", [])),
        }
        for gate, report in sorted(gate_reports.items())
    }
    return json.dumps(slim, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


class RegressionProtector:
    """Baseline imutável por sessão — drift = FAIL."""

    def __init__(self) -> None:
        self._baseline_hash: str | None = None
        self._baseline_status: dict[str, str] = {}

    def set_baseline(self, gate_reports: dict[str, dict[str, Any]]) -> None:
        self._baseline_hash = hashlib.sha256(
            _canonical_gate_slice(gate_reports).encode("utf-8")
        ).hexdigest()
        self._baseline_status = {
            gate: report.get("status", "UNKNOWN")
            for gate, report in sorted(gate_reports.items())
        }

    def detect_behavior_shift(
        self,
        gate_reports: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        failures: list[str] = []
        current_hash = hashlib.sha256(
            _canonical_gate_slice(gate_reports).encode("utf-8")
        ).hexdigest()

        if self._baseline_hash is None:
            self.set_baseline(gate_reports)
            return {"status": "PASS", "failures": [], "baseline_established": True}

        if current_hash != self._baseline_hash:
            failures.append(
                f"behavior_shift: hash diverge "
                f"({self._baseline_hash[:12]}… != {current_hash[:12]}…)."
            )

        for gate, baseline_status in self._baseline_status.items():
            current = gate_reports.get(gate, {}).get("status", "MISSING")
            if baseline_status == "PASS" and current != "PASS":
                failures.append(f"behavior_shift:{gate}:{baseline_status}->{current}.")

        ordered = sorted(failures)
        return {
            "status": "PASS" if not ordered else "FAIL",
            "failures": ordered,
            "shift_detected": bool(ordered),
        }

    def validate_output_consistency(
        self,
        gate_reports: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        failures: list[str] = []

        hashes = [
            hashlib.sha256(_canonical_gate_slice(gate_reports).encode("utf-8")).hexdigest()
            for _ in range(2)
        ]
        if len(set(hashes)) != 1:
            failures.append("consistency: hash instável em recompute duplo.")

        shift = self.detect_behavior_shift(gate_reports)
        failures.extend(shift["failures"])

        ordered = sorted(set(failures))
        return {
            "status": "PASS" if not ordered else "FAIL",
            "failures": ordered,
        }
