"""
audit_event_bus.py — barramento de eventos de auditoria determinístico.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from src.observability.run_logger import _hash_payload, derive_step_timestamp

AuditHandler = Callable[["AuditEvent"], None]


class AuditEventType(str, Enum):
    CONTRACT_REGISTERED = "CONTRACT_REGISTERED"
    DATASET_REGISTERED = "DATASET_REGISTERED"
    SNAPSHOT_CREATED = "SNAPSHOT_CREATED"
    CI_GATE_PASSED = "CI_GATE_PASSED"
    CI_GATE_FAILED = "CI_GATE_FAILED"


@dataclass(frozen=True)
class AuditEvent:
    event_type: AuditEventType
    payload: dict[str, Any]
    sequence: int
    derived_timestamp: str
    event_hash: str

    @classmethod
    def create(
        cls,
        event_type: AuditEventType | str,
        payload: dict[str, Any],
        *,
        sequence: int,
    ) -> AuditEvent:
        if isinstance(event_type, str):
            event_type = AuditEventType(event_type)
        canonical = dict(sorted(payload.items(), key=lambda kv: str(kv[0])))
        body = {
            "event_type": event_type.value,
            "payload": canonical,
            "sequence": int(sequence),
        }
        return cls(
            event_type=event_type,
            payload=canonical,
            sequence=int(sequence),
            derived_timestamp=derive_step_timestamp(sequence),
            event_hash=_hash_payload(body),
        )


@dataclass
class AuditEventBus:
    """
    Bus append-only de eventos de auditoria.

    Handlers executados em ordem determinística de registro.
    """

    _handlers: list[tuple[str, AuditHandler]] = field(default_factory=list)
    _events: list[AuditEvent] = field(default_factory=list)
    _sequence: int = field(default=0)

    def subscribe(self, handler: AuditHandler, *, handler_id: str | None = None) -> str:
        hid = handler_id or f"handler-{len(self._handlers):04d}"
        if any(existing_id == hid for existing_id, _ in self._handlers):
            raise ValueError(f"handler_id duplicado: {hid!r}.")
        self._handlers.append((hid, handler))
        self._handlers.sort(key=lambda item: item[0])
        return hid

    def emit(
        self,
        event_type: AuditEventType | str,
        payload: dict[str, Any],
    ) -> AuditEvent:
        self._sequence += 1
        event = AuditEvent.create(
            event_type,
            payload,
            sequence=self._sequence,
        )
        self._events.append(event)
        for _, handler in self._handlers:
            handler(event)
        return event

    def list_events(
        self,
        event_type: AuditEventType | str | None = None,
    ) -> list[AuditEvent]:
        if event_type is None:
            return list(self._events)
        if isinstance(event_type, str):
            event_type = AuditEventType(event_type)
        return [e for e in self._events if e.event_type == event_type]

    def event_log_hash(self) -> str:
        """Hash determinístico de todos os eventos emitidos."""
        return _hash_payload(
            {
                "events": [
                    {
                        "event_type": e.event_type.value,
                        "payload": e.payload,
                        "sequence": e.sequence,
                        "event_hash": e.event_hash,
                    }
                    for e in self._events
                ]
            }
        )

    def clear(self) -> None:
        """Reset (somente testes)."""
        self._handlers.clear()
        self._events.clear()
        self._sequence = 0
