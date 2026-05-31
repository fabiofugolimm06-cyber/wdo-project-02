"""
production_engine.py — engine de execução production fora do CI.
"""

from __future__ import annotations

import os
from typing import Any

from src.runtime.execution_context import ExecutionContext
from src.runtime.run_controller import RunController


class ProductionEngine:
    """Executa pipeline como sistema real — rastreável e com fingerprint."""

    def __init__(self) -> None:
        self._context: ExecutionContext | None = None
        self._controller = RunController()

    def attach_registry_state(self, context: ExecutionContext | None = None) -> dict[str, Any]:
        ctx = context or self._context or ExecutionContext()
        ctx.bind_contract_registry()
        ctx.initialize_snapshot_state()

        from src.observability import SystemFingerprintLogger

        logger = SystemFingerprintLogger()
        ctx.run_fingerprint = logger.compute_system_fingerprint()
        self._context = ctx
        return {
            "contracts_fingerprint": logger.compute_contracts_fingerprint(),
            "data_fingerprint": logger.compute_data_fingerprint(),
            "system_fingerprint": ctx.run_fingerprint,
            "snapshot_state": dict(ctx.snapshot_state),
        }

    def execute_pipeline(self, *, snapshot_runs: int = 5) -> dict[str, Any]:
        ctx = ExecutionContext()
        ctx.load_environment_config()
        self.attach_registry_state(ctx)

        run = self._controller.start_run(ctx)
        old_ci = os.environ.pop("WDO_CI", None)
        try:
            from src.api.pipeline_endpoint import PipelineEndpoint

            result = PipelineEndpoint().execute_full_pipeline(
                snapshot_runs=snapshot_runs,
            )
        finally:
            if old_ci is not None:
                os.environ["WDO_CI"] = old_ci

        self._controller.stop_run()
        status = result.get("status", "FAIL")
        return {
            "status": status,
            "failures": result.get("failures", []),
            "fingerprint": result.get("fingerprint", ctx.run_fingerprint),
            "run": run,
            "reports": result.get("reports", {}),
            "context": ctx.to_dict(),
        }

    def run_live_mode(self, *, snapshot_runs: int = 5) -> dict[str, Any]:
        from src.release import ReleaseController

        ReleaseController().set_mode("prod")
        os.environ.setdefault("WDO_RELEASE_MODE", "prod")
        return self.execute_pipeline(snapshot_runs=snapshot_runs)
