"""
run_logger.py — logger determinístico de execução (sem clock real).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Mapping

WDO_DERIVED_EPOCH = "2000-01-01T00:00:00Z"


def derive_step_timestamp(step_index: int) -> str:
    """Timestamp derivado deterministicamente (nunca ``datetime.now()``)."""
    if step_index < 0:
        raise ValueError(f"step_index deve ser >= 0, got {step_index}.")
    return f"{WDO_DERIVED_EPOCH}#step-{int(step_index):04d}"


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _hash_payload(obj: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(dict(obj)).encode("utf-8")).hexdigest()


@dataclass
class RunLogger:
    """
    Logger de run reprodutível.

    ``run_id`` e ``run_hash`` derivam do contexto + steps (sem timestamps reais).
    """

    run_id: str = ""
    context: dict[str, Any] = field(default_factory=dict)
    steps: list[dict[str, Any]] = field(default_factory=list)
    status: str | None = None
    _step_counter: int = field(default=0, repr=False)

    def log_run(self, context: Mapping[str, Any]) -> dict[str, Any]:
        """Inicializa run com contexto canônico."""
        self.context = dict(sorted(context.items(), key=lambda kv: str(kv[0])))
        self.run_id = _hash_payload({"context": self.context})[:16]
        self.steps = []
        self.status = None
        self._step_counter = 0
        entry = {
            "run_id": self.run_id,
            "derived_timestamp": derive_step_timestamp(0),
            "context": dict(self.context),
        }
        return entry

    def log_step(self, step_name: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        """Registra passo ordenado com timestamp derivado."""
        if not self.run_id:
            raise RuntimeError("RunLogger: chame log_run() antes de log_step().")
        self._step_counter += 1
        canonical_payload = dict(sorted(payload.items(), key=lambda kv: str(kv[0])))
        entry = {
            "run_id": self.run_id,
            "step_index": self._step_counter,
            "step_name": step_name,
            "derived_timestamp": derive_step_timestamp(self._step_counter),
            "payload": canonical_payload,
            "step_hash": _hash_payload(
                {"step_name": step_name, "payload": canonical_payload}
            ),
        }
        self.steps.append(entry)
        return entry

    def finalize_run(self, status: str) -> dict[str, Any]:
        """Finaliza run com status e hash global."""
        if not self.run_id:
            raise RuntimeError("RunLogger: chame log_run() antes de finalize_run().")
        normalized = status.strip().upper()
        if normalized not in {"PASS", "FAIL", "RUNNING"}:
            raise ValueError(f"status inválido: {status!r}.")
        self.status = normalized
        record = self.to_dict()
        record["run_hash"] = self.run_hash
        return record

    @property
    def run_hash(self) -> str:
        """Hash SHA256 determinístico do run completo."""
        return _hash_payload(
            {
                "run_id": self.run_id,
                "context": self.context,
                "steps": self.steps,
                "status": self.status,
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "context": dict(self.context),
            "steps": list(self.steps),
            "status": self.status,
            "run_hash": self.run_hash if self.run_id else None,
        }
