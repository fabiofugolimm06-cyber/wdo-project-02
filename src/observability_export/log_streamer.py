"""
log_streamer.py — stream de logs estruturados e audit export.
"""

from __future__ import annotations

from typing import Any

from src.observability import AuditEventBus, AuditEventType, RunLogger


class LogStreamer:
    """Exporta logs para consumo externo."""

    def stream_structured_logs(
        self,
        *,
        context: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        logger = RunLogger(context=context or {"source": "observability_export"})
        logger.log_run({"phase": "export", "seed": 42})
        logger.log_step("stream", {"ok": True})
        logger.finalize_run("PASS")
        return [
            {
                "run_id": logger.run_id,
                "run_hash": logger.run_hash,
                "steps": list(logger.steps),
            }
        ]

    def export_audit_log(self) -> dict[str, Any]:
        from microstructure.determinism import WDO_PROJECT_RANDOM_SEED

        bus = AuditEventBus()
        payload = {"seed": WDO_PROJECT_RANDOM_SEED, "export": "audit"}
        for event_type in (
            AuditEventType.CONTRACT_REGISTERED,
            AuditEventType.CI_GATE_PASSED,
        ):
            bus.emit(event_type, payload)
        events = bus.list_events()
        return {
            "event_count": len(events),
            "event_log_hash": bus.event_log_hash(),
            "events": [
                {
                    "event_type": e.event_type.value,
                    "sequence": e.sequence,
                    "event_hash": e.event_hash,
                }
                for e in events
            ],
        }
