"""
wdo_api.py — API pública do sistema WDO.
"""

from __future__ import annotations

from typing import Any

from src.api.health_endpoint import HealthEndpoint
from src.api.pipeline_endpoint import PipelineEndpoint
from src.runtime.production_engine import ProductionEngine


class WDOApi:
    """Superfície externa — serviço acessível fora do CI."""

    def __init__(self) -> None:
        self._pipeline = PipelineEndpoint()
        self._health = HealthEndpoint()
        self._engine = ProductionEngine()

    def run_pipeline(self, *, snapshot_runs: int = 5) -> dict[str, Any]:
        return self._engine.execute_pipeline(snapshot_runs=snapshot_runs)

    def get_latest_snapshot(self) -> dict[str, Any]:
        from src.snapshot_spec.snapshot_registry import bootstrap_baseline_snapshot_registry

        registry = bootstrap_baseline_snapshot_registry()
        snapshots = registry.list()
        if not snapshots:
            return {"status": "FAIL", "failures": ["snapshot: nenhum baseline."]}
        latest = snapshots[-1]
        return {
            "status": "PASS",
            "failures": [],
            "snapshot_id": latest.snapshot_id,
            "state_hash": latest.state_hash,
            "pipeline_stage": latest.pipeline_stage,
        }

    def get_system_health(self, *, snapshot_runs: int = 5) -> dict[str, Any]:
        return self._health.return_system_health_score(snapshot_runs=snapshot_runs)

    def execute_gate(self, gate_name: str, *, snapshot_runs: int = 5) -> dict[str, Any]:
        return self._pipeline.execute_gate(gate_name, snapshot_runs=snapshot_runs)
