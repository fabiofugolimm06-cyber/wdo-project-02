"""
run_controller.py — controle de runs production (start/stop/restart).
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from src.runtime.execution_context import ExecutionContext


class RunController:
    """Todo run tem fingerprint e histórico rastreável."""

    _instance: RunController | None = None

    def __new__(cls) -> RunController:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._active_run = None
            cls._instance._history = []
        return cls._instance

    def start_run(self, context: ExecutionContext) -> dict[str, Any]:
        from src.observability import SystemFingerprintLogger

        fingerprint = SystemFingerprintLogger().compute_system_fingerprint()
        context.run_fingerprint = fingerprint

        payload = json.dumps(context.to_dict(), sort_keys=True, separators=(",", ":"))
        run_id = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

        run = {
            "run_id": run_id,
            "fingerprint": fingerprint,
            "status": "running",
            "snapshot_id": context.snapshot_state.get("baseline_snapshot_id"),
        }
        self._active_run = run
        self._history.append(dict(run))
        return dict(run)

    def stop_run(self) -> dict[str, Any]:
        if self._active_run is None:
            return {"status": "idle", "failures": ["run: nenhum run ativo."]}
        self._active_run["status"] = "stopped"
        return dict(self._active_run)

    def restart_from_snapshot(self, *, snapshot_id: str | None = None) -> dict[str, Any]:
        context = ExecutionContext()
        context.load_environment_config()
        context.bind_contract_registry()
        context.initialize_snapshot_state()
        if snapshot_id:
            context.snapshot_state["baseline_snapshot_id"] = snapshot_id
        if self._active_run and self._active_run.get("status") == "running":
            self.stop_run()
        return self.start_run(context)

    def get_active_run(self) -> dict[str, Any] | None:
        return dict(self._active_run) if self._active_run else None

    def list_history(self) -> list[dict[str, Any]]:
        return list(self._history)

    @classmethod
    def reset(cls) -> None:
        cls._instance = None
