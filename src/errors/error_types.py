"""
error_types.py — tipos estruturais de erro do sistema.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class ErrorType(str, Enum):
    CONTRACT_VIOLATION = "CONTRACT_VIOLATION"
    DATA_DRIFT = "DATA_DRIFT"
    SNAPSHOT_MISMATCH = "SNAPSHOT_MISMATCH"
    EVOLUTION_BREAKING = "EVOLUTION_BREAKING"
    CI_FAILURE = "CI_FAILURE"
    SYSTEM_LOCK_VIOLATION = "SYSTEM_LOCK_VIOLATION"
    CONFIG_DRIFT = "CONFIG_DRIFT"
    RUNTIME_MUTATION = "RUNTIME_MUTATION"
    UNKNOWN = "UNKNOWN"


class ErrorLayer(str, Enum):
    CONTRACTS = "contracts"
    DATA = "data"
    EVOLUTION = "evolution"
    SNAPSHOT = "snapshot"
    CI = "ci"
    SYSTEM_LOCK = "system_lock"
    CONFIG = "config"
    RUNTIME = "runtime"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ClassifiedError:
    error_type: ErrorType
    layer: ErrorLayer
    message: str
    signature: str
    origin: str
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "error_type": self.error_type.value,
            "layer": self.layer.value,
            "message": self.message,
            "signature": self.signature,
            "origin": self.origin,
            "payload": dict(self.payload),
        }
