"""
pipeline_endpoint.py — execução de pipeline e gates individuais.
"""

from __future__ import annotations

from typing import Any, Callable


class PipelineEndpoint:
    """Endpoint de execução — core path sem dependência de CI gate chain."""

    _GATE_RUNNERS: dict[str, Callable[..., dict[str, Any]]] | None = None

    def _runners(self) -> dict[str, Callable[..., dict[str, Any]]]:
        if self._GATE_RUNNERS is None:
            from src.ci import ContractCIGate, DataCIGate
            from src.evolution.evolution_registry import validate_evolution_ci
            from src.snapshot_spec import SnapshotCIGate

            type(self)._GATE_RUNNERS = {
                "contract-gate": ContractCIGate().run_full_contract_check,
                "evolution-gate": validate_evolution_ci,
                "data-gate": DataCIGate().run_full_data_check,
                "snapshot-spec-gate": lambda snapshot_runs=5: SnapshotCIGate(
                    seed=42,
                    snapshot_runs=snapshot_runs,
                ).run_full_snapshot_spec_check(),
            }
        return self._GATE_RUNNERS

    def execute_full_pipeline(self, *, snapshot_runs: int = 5) -> dict[str, Any]:
        reports: dict[str, dict[str, Any]] = {}
        failures: list[str] = []

        for gate, runner in self._runners().items():
            if gate == "snapshot-spec-gate":
                report = runner(snapshot_runs=snapshot_runs)
            else:
                report = runner()
            reports[gate] = report
            if report.get("status") != "PASS":
                failures.extend(report.get("failures", []))

        from src.observability import SystemFingerprintLogger

        fingerprint = SystemFingerprintLogger().compute_system_fingerprint()
        ordered = sorted(set(failures))
        return {
            "status": "PASS" if not ordered else "FAIL",
            "failures": ordered,
            "reports": reports,
            "fingerprint": fingerprint,
        }

    def execute_gate(
        self,
        gate_name: str,
        *,
        snapshot_runs: int = 5,
    ) -> dict[str, Any]:
        runners = self._runners()
        if gate_name not in runners:
            return {
                "status": "FAIL",
                "failures": [f"gate desconhecido: {gate_name!r}."],
            }
        runner = runners[gate_name]
        if gate_name == "snapshot-spec-gate":
            return runner(snapshot_runs=snapshot_runs)
        return runner()
