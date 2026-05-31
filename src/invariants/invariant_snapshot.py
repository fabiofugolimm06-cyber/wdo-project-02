"""
invariant_snapshot.py — snapshot imutável de invariantes do sistema.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping


def compute_invariant_set_hash(invariant_set: Mapping[str, Any]) -> str:
    payload = json.dumps(dict(invariant_set), sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class InvariantSnapshot:
    snapshot_id: str
    system_state_hash: str
    invariant_set: dict[str, Any]
    validation_results: dict[str, Any]

    @property
    def invariant_set_hash(self) -> str:
        return compute_invariant_set_hash(self.invariant_set)

    @classmethod
    def build(
        cls,
        *,
        snapshot_id: str,
        system_state_hash: str,
        invariant_set: Mapping[str, Any],
        validation_results: Mapping[str, Any] | None = None,
    ) -> InvariantSnapshot:
        return cls(
            snapshot_id=snapshot_id,
            system_state_hash=system_state_hash,
            invariant_set=dict(invariant_set),
            validation_results=dict(validation_results or {}),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "system_state_hash": self.system_state_hash,
            "invariant_set": dict(self.invariant_set),
            "invariant_set_hash": self.invariant_set_hash,
            "validation_results": dict(self.validation_results),
        }
