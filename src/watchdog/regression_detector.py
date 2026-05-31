"""
regression_detector.py — detecção de regressão vs baseline determinístico.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RegressionDetector:
    """Compara runs atuais vs baseline hash — regressão isolada por layer."""

    _baseline_run_hash: str | None = None
    _baseline_gate_status: dict[str, str] = field(default_factory=dict)

    def set_baseline(
        self,
        *,
        run_hash: str,
        gate_reports: dict[str, dict[str, Any]],
    ) -> None:
        self._baseline_run_hash = run_hash
        self._baseline_gate_status = {
            gate: report.get("status", "UNKNOWN")
            for gate, report in sorted(gate_reports.items())
        }

    def compare_baseline_runs(
        self,
        *,
        run_hash: str,
        gate_reports: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        failures: list[str] = []
        if self._baseline_run_hash is None:
            failures.append("baseline: não definido.")
            return {"status": "FAIL", "failures": failures, "regression": False}

        if run_hash != self._baseline_run_hash:
            failures.append(
                f"regression: run_hash diverge "
                f"({self._baseline_run_hash[:12]}… != {run_hash[:12]}…)."
            )

        for gate, baseline_status in self._baseline_gate_status.items():
            current = gate_reports.get(gate, {}).get("status", "MISSING")
            if baseline_status == "PASS" and current != "PASS":
                failures.append(f"regression:{gate}: {baseline_status}->{current}.")

        ordered = sorted(failures)
        return {
            "status": "PASS" if not ordered else "FAIL",
            "failures": ordered,
            "regression": bool(ordered),
        }

    def detect_new_failures(
        self,
        gate_reports: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        failures: list[str] = []
        new_failures: list[str] = []

        for gate, report in sorted(gate_reports.items()):
            if report.get("status") != "PASS":
                for msg in report.get("failures", []):
                    entry = f"{gate}:{msg}"
                    new_failures.append(entry)
                    failures.append(f"new_failure:{entry}")

        if self._baseline_gate_status:
            for gate, status in self._baseline_gate_status.items():
                if status == "PASS":
                    current = gate_reports.get(gate, {}).get("status")
                    if current == "FAIL":
                        failures.append(f"regression_layer:{gate}")

        ordered = sorted(set(failures))
        return {
            "status": "PASS" if not ordered else "FAIL",
            "failures": ordered,
            "new_failures": sorted(new_failures),
        }

    def flag_regression(
        self,
        *,
        run_hash: str,
        gate_reports: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        baseline_cmp = self.compare_baseline_runs(
            run_hash=run_hash,
            gate_reports=gate_reports,
        )
        new_fail = self.detect_new_failures(gate_reports)
        failures = sorted(set(baseline_cmp["failures"] + new_fail["failures"]))
        return {
            "status": "PASS" if not failures else "FAIL",
            "failures": failures,
            "regression_detected": bool(failures),
        }
