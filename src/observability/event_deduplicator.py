"""
event_deduplicator.py — deduplicação de eventos de auditoria.
"""

from __future__ import annotations

from typing import Any

from src.observability.audit_event_bus import AuditEvent, AuditEventType
from src.observability.trace_compressor import TraceCompressor


class EventDeduplicator:
    """Merge de assinaturas idênticas sem perda semântica."""

    def deduplicate_audit_events(self, events: list[AuditEvent]) -> list[dict[str, Any]]:
        merged: list[dict[str, Any]] = []
        signature_index: dict[str, int] = {}

        for event in events:
            semantic = {
                "event_type": event.event_type.value,
                "payload": event.payload,
            }
            sig = TraceCompressor._hash_payload(semantic)
            if sig in signature_index:
                idx = signature_index[sig]
                merged[idx]["occurrence_count"] += 1
                merged[idx]["sequences"].append(event.sequence)
            else:
                signature_index[sig] = len(merged)
                merged.append(
                    {
                        "event_type": event.event_type.value,
                        "payload": event.payload,
                        "event_hash": event.event_hash,
                        "occurrence_count": 1,
                        "sequences": [event.sequence],
                    }
                )
        return merged

    def merge_identical_signatures(
        self,
        events: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        raw_events = [
            {
                "event_type": e.get("event_type", ""),
                "payload": e.get("payload", {}),
            }
            for e in events
        ]
        return TraceCompressor().remove_redundant_events(raw_events)

    def deduplicated_log_hash(self, events: list[AuditEvent]) -> str:
        merged = self.deduplicate_audit_events(events)
        return TraceCompressor._hash_payload({"merged_events": merged})
