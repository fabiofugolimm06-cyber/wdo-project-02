"""
ci_watchdog.py — watchdog de estabilidade CI.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from src.watchdog.pipeline_monitor import PipelineMonitor
from src.watchdog.regression_detector import RegressionDetector


def _hash_reports(reports: dict[str, dict[str, Any]]) -> str:
    payload = json.dumps(
        {k: {"status": v.get("status"), "failures": v.get("failures", [])}
         for k, v in sorted(reports.items())},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass
class CIWatchdog:
    """
    Monitor de estabilidade CI — flakiness = FAIL estrutural.

    ``stability_runs`` execuções idênticas devem produzir mesmo run_hash.
    """

    stability_runs: int = 3
    stability_threshold: float = 1.0
    monitor: PipelineMonitor = field(default_factory=PipelineMonitor)
    regression: RegressionDetector = field(default_factory=RegressionDetector)

    def monitor_pipeline_runs(
        self,
        runner: Any,
        *,
        snapshot_runs: int = 5,
    ) -> dict[str, Any]:
        hashes: list[str] = []
        last_reports: dict[str, dict[str, Any]] = {}

        for idx in range(self.stability_runs):
            reports = runner(snapshot_runs=snapshot_runs)
            gate_reports = {
                k: v for k, v in reports.items() if k.endswith("-gate")
            }
            run_hash = _hash_reports(gate_reports)
            hashes.append(run_hash)
            last_reports = gate_reports
            self.monitor.record_run(
                run_id=f"watchdog-{idx + 1}",
                run_hash=run_hash,
                gate_reports=gate_reports,
            )

        if len(set(hashes)) != 1:
            return {
                "status": "FAIL",
                "failures": [
                    f"ci_instability: {len(set(hashes))} hashes distintos "
                    f"em {self.stability_runs} runs."
                ],
                "run_hashes": hashes,
            }

        baseline_hash = hashes[0]
        if self.regression._baseline_run_hash is None:
            self.regression.set_baseline(
                run_hash=baseline_hash,
                gate_reports=last_reports,
            )

        return {
            "status": "PASS",
            "failures": [],
            "run_hash": baseline_hash,
            "gate_reports": last_reports,
        }

    def detect_ci_instability(self) -> dict[str, Any]:
        flaky = self.monitor.detect_flaky_gate(threshold=self.stability_threshold)
        return flaky

    def enforce_ci_stability_threshold(self) -> dict[str, Any]:
        stats = self.monitor.track_run_success_rate()
        failures: list[str] = []
        if stats["total_runs"] == 0:
            failures.append("watchdog: nenhum run registrado.")
        elif stats["success_rate"] < self.stability_threshold:
            failures.append(
                f"watchdog: success_rate={stats['success_rate']:.4f} "
                f"< {self.stability_threshold}."
            )
        flaky = self.detect_ci_instability()
        if flaky["status"] == "FAIL":
            failures.extend(flaky["failures"])
        ordered = sorted(failures)
        return {
            "status": "PASS" if not ordered else "FAIL",
            "failures": ordered,
            "success_rate": stats.get("success_rate", 0.0),
        }


def run_watchdog_gate(
    *,
    gate_reports: dict[str, dict[str, Any]] | None = None,
    run_hash: str | None = None,
) -> dict[str, Any]:
    """Gate CI — watchdog-gate (estabilidade + anti-regressão)."""
    watchdog = CIWatchdog(stability_runs=2, stability_threshold=1.0)
    failures: list[str] = []

    if gate_reports is None:
        from scripts.run_architecture_gate import run_architecture_gate

        monitored = watchdog.monitor_pipeline_runs(
            run_architecture_gate,
            snapshot_runs=5,
        )
        if monitored["status"] == "FAIL":
            return monitored
        gate_reports = monitored["gate_reports"]
        run_hash = monitored["run_hash"]

    assert gate_reports is not None

    # Determinismo: hash de reports idêntico em recálculos
    hash_a = _hash_reports(gate_reports)
    hash_b = _hash_reports(gate_reports)
    if hash_a != hash_b:
        failures.append("watchdog: gate_reports hash instável.")

    run_hash = run_hash or hash_a
    for idx in range(2):
        watchdog.monitor.record_run(
            run_id=f"pipeline-{idx + 1}",
            run_hash=run_hash,
            gate_reports=gate_reports,
        )

    stability = watchdog.enforce_ci_stability_threshold()
    if stability["status"] == "FAIL":
        failures.extend(stability["failures"])

    if watchdog.regression._baseline_run_hash is None:
        watchdog.regression.set_baseline(
            run_hash=run_hash,
            gate_reports=gate_reports,
        )

    regression = watchdog.regression.flag_regression(
        run_hash=run_hash,
        gate_reports=gate_reports,
    )
    if regression["status"] == "FAIL":
        failures.extend(regression["failures"])

    ordered = sorted(set(failures))
    return {
        "status": "PASS" if not ordered else "FAIL",
        "failures": ordered,
        "run_hash": run_hash,
    }
