"""
failure_registry.py — registry estrutural de falhas rastreáveis.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.errors.error_types import ClassifiedError, ErrorLayer, ErrorType


@dataclass(frozen=True)
class FailureRecord:
    sequence: int
    classified: ClassifiedError
    gate: str
    run_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "gate": self.gate,
            "run_id": self.run_id,
            **self.classified.to_dict(),
        }


@dataclass
class FailureRegistry:
    """Append-only registry de falhas — origem sempre rastreável."""

    _records: list[FailureRecord] = field(default_factory=list)
    _sequence: int = field(default=0)

    def register_failure(
        self,
        classified: ClassifiedError,
        *,
        gate: str,
        run_id: str,
    ) -> FailureRecord:
        self._sequence += 1
        record = FailureRecord(
            sequence=self._sequence,
            classified=classified,
            gate=gate,
            run_id=run_id,
        )
        self._records.append(record)
        return record

    def get_failure_history(
        self,
        *,
        layer: ErrorLayer | None = None,
        error_type: ErrorType | None = None,
    ) -> list[FailureRecord]:
        records = list(self._records)
        if layer is not None:
            records = [r for r in records if r.classified.layer == layer]
        if error_type is not None:
            records = [r for r in records if r.classified.error_type == error_type]
        return records

    def compute_failure_rate(self) -> dict[str, Any]:
        total = len(self._records)
        if total == 0:
            return {"total": 0, "rate_by_layer": {}, "rate_by_type": {}}

        by_layer: dict[str, int] = {}
        by_type: dict[str, int] = {}
        for record in self._records:
            layer = record.classified.layer.value
            etype = record.classified.error_type.value
            by_layer[layer] = by_layer.get(layer, 0) + 1
            by_type[etype] = by_type.get(etype, 0) + 1

        return {
            "total": total,
            "rate_by_layer": {k: v / total for k, v in sorted(by_layer.items())},
            "rate_by_type": {k: v / total for k, v in sorted(by_type.items())},
        }

    def clear(self) -> None:
        self._records.clear()
        self._sequence = 0
