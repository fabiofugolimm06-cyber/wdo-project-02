"""
system_health_monitor.py — monitor agregado de saúde do sistema.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.health.consistency_checker import ConsistencyChecker
from src.health.invariant_validator import InvariantValidator


def _report(failures: list[str], *, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    ordered = sorted(failures)
    out: dict[str, Any] = {
        "status": "PASS" if not ordered else "FAIL",
        "failures": ordered,
    }
    if extra:
        out.update(extra)
    return out


@dataclass
class SystemHealthMonitor:
    """
    Agrega checks de integridade de todas as camadas.

    CHECKS: contracts, data, evolution, snapshots, CI consistency.
    """

    snapshot_runs: int = 20
    _checks: dict[str, dict[str, Any]] = field(default_factory=dict)

    def validate_all_layers(self) -> dict[str, Any]:
        failures: list[str] = []
        self._checks = {}

        from src.ci import ContractCIGate, DataCIGate, SnapshotCIGate

        layer_runners = {
            "contract_integrity": lambda: ContractCIGate().run_full_contract_check(),
            "data_integrity": lambda: DataCIGate().run_full_data_check(),
            "evolution_chain_integrity": lambda: __import__(
                "src.evolution.evolution_registry",
                fromlist=["validate_evolution_ci"],
            ).validate_evolution_ci(),
            "snapshot_determinism": lambda: SnapshotCIGate().run_full_snapshot_check(
                snapshot_runs=self.snapshot_runs,
            ),
            "ci_consistency": lambda: InvariantValidator().validate_system_invariants(),
        }

        for name, runner in layer_runners.items():
            report = runner()
            self._checks[name] = report
            if report.get("status") == "FAIL":
                failures.extend(
                    f"{name}:{msg}" for msg in report.get("failures", [])
                )

        cross = ConsistencyChecker().detect_cross_layer_drift()
        self._checks["cross_layer"] = cross
        if cross["status"] == "FAIL":
            failures.extend(cross["failures"])

        return _report(failures, extra={"checks": self._checks})

    def compute_health_score(self) -> int:
        """Score 0–100 determinístico (% checks PASS)."""
        if not self._checks:
            self.validate_all_layers()
        total = len(self._checks)
        if total == 0:
            return 0
        passed = sum(
            1 for report in self._checks.values() if report.get("status") == "PASS"
        )
        return int((passed / total) * 100)

    def run_full_health_check(self) -> dict[str, Any]:
        report = self.validate_all_layers()
        score = self.compute_health_score()
        report["health_score"] = score
        report["healthy"] = report["status"] == "PASS" and score == 100
        return report


def run_system_health_gate(*, snapshot_runs: int = 20) -> dict[str, Any]:
    """Gate CI — system-health-gate."""
    monitor = SystemHealthMonitor(snapshot_runs=snapshot_runs)
    report = monitor.run_full_health_check()
    return {
        "status": report["status"],
        "failures": report["failures"],
        "health_score": report["health_score"],
    }
