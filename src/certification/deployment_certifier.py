"""
deployment_certifier.py — certificação de readiness, rollback e API.
"""

from __future__ import annotations

import os
from typing import Any


class DeploymentCertifier:
    """Certifica capacidade de deploy e operação externa."""

    def certify_production_readiness(self) -> dict[str, Any]:
        from src.runtime import ProductionEngine

        old_ci = os.environ.pop("WDO_CI", None)
        failures: list[str] = []
        try:
            result = ProductionEngine().execute_pipeline(snapshot_runs=3)
            if result["status"] != "PASS":
                failures.extend(result.get("failures", []))
            if not result.get("fingerprint"):
                failures.append("readiness: fingerprint ausente.")
        finally:
            if old_ci is not None:
                os.environ["WDO_CI"] = old_ci

        ordered = sorted(set(failures))
        return {
            "status": "PASS" if not ordered else "FAIL",
            "failures": ordered,
            "runtime_executable": not ordered,
        }

    def certify_rollback_capability(self) -> dict[str, Any]:
        from src.deployment import RollbackManager, ReleaseManager

        fp = "cert" + "0" * 60
        ReleaseManager().deploy_version(version="1.0.0", fingerprint=fp)
        failures: list[str] = []
        for _ in range(3):
            report = RollbackManager().rollback_to_version(version="1.0.0")
            if report["status"] != "PASS":
                failures.extend(report.get("failures", []))

        restore = RollbackManager().restore_snapshot_state()
        if restore["status"] != "PASS":
            failures.extend(restore.get("failures", []))

        ordered = sorted(set(failures))
        return {
            "status": "PASS" if not ordered else "FAIL",
            "failures": ordered,
            "rollback_functional": not ordered,
        }

    def certify_external_api(self) -> dict[str, Any]:
        from src.api import WDOApi

        api = WDOApi()
        failures: list[str] = []

        snapshot = api.get_latest_snapshot()
        if snapshot["status"] != "PASS":
            failures.extend(snapshot.get("failures", []))

        health = api.get_system_health(snapshot_runs=3)
        if health["status"] != "PASS":
            failures.extend(health.get("failures", []))

        gate = api.execute_gate("contract-gate")
        if gate["status"] != "PASS":
            failures.extend(gate.get("failures", []))

        ordered = sorted(set(failures))
        return {
            "status": "PASS" if not ordered else "FAIL",
            "failures": ordered,
            "api_operational": not ordered,
        }
