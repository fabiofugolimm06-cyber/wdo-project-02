"""
rollback_controller.py — rollback para último estado estável.
"""

from __future__ import annotations

from typing import Any


class RollbackController:
    """Restaura snapshot baseline em caso de falha estrutural."""

    def rollback_to_last_stable_state(
        self,
        *,
        gate_reports: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        failures: list[str] = []
        stable = all(r.get("status") == "PASS" for r in gate_reports.values())
        if not stable:
            failures.append("rollback: pipeline não estável para baseline.")

        snapshot = self.restore_snapshot()
        if snapshot["status"] == "FAIL":
            failures.extend(snapshot["failures"])

        ordered = sorted(set(failures))
        return {
            "status": "PASS" if not ordered else "FAIL",
            "failures": ordered,
            "snapshot": snapshot,
            "stable": stable,
        }

    def restore_snapshot(self) -> dict[str, Any]:
        from src.snapshot_spec.snapshot_registry import bootstrap_baseline_snapshot_registry

        registry = bootstrap_baseline_snapshot_registry()
        snapshots = registry.list()
        if not snapshots:
            return {"status": "FAIL", "failures": ["rollback: nenhum snapshot baseline."]}

        spec = snapshots[0]
        return {
            "status": "PASS",
            "failures": [],
            "snapshot_id": spec.snapshot_id,
            "state_hash": spec.state_hash,
            "pipeline_stage": spec.pipeline_stage,
        }
