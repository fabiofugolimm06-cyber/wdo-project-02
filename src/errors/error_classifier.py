"""
error_classifier.py — classificação e assinatura determinística de erros.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from src.errors.error_types import ClassifiedError, ErrorLayer, ErrorType


class ErrorClassifier:
    """Mapeia exceções e mensagens de gate para taxonomia estrutural."""

    _PATTERNS: tuple[tuple[re.Pattern[str], ErrorType, ErrorLayer], ...] = (
        (re.compile(r"contract", re.I), ErrorType.CONTRACT_VIOLATION, ErrorLayer.CONTRACTS),
        (re.compile(r"data|dataset|fingerprint", re.I), ErrorType.DATA_DRIFT, ErrorLayer.DATA),
        (re.compile(r"snapshot|spec", re.I), ErrorType.SNAPSHOT_MISMATCH, ErrorLayer.SNAPSHOT),
        (re.compile(r"evolution|migration|breaking", re.I), ErrorType.EVOLUTION_BREAKING, ErrorLayer.EVOLUTION),
        (re.compile(r"runtime|prod_lock|prod mode", re.I), ErrorType.RUNTIME_MUTATION, ErrorLayer.RUNTIME),
        (re.compile(r"system.?lock|freeze", re.I), ErrorType.SYSTEM_LOCK_VIOLATION, ErrorLayer.SYSTEM_LOCK),
        (re.compile(r"config", re.I), ErrorType.CONFIG_DRIFT, ErrorLayer.CONFIG),
        (re.compile(r"ci|gate|pipeline", re.I), ErrorType.CI_FAILURE, ErrorLayer.CI),
    )

    def classify_error(
        self,
        exc: BaseException | str,
        *,
        origin: str = "unknown",
        payload: dict[str, Any] | None = None,
    ) -> ClassifiedError:
        message = str(exc)
        error_type = ErrorType.UNKNOWN
        layer = ErrorLayer.UNKNOWN

        for pattern, etype, elayer in self._PATTERNS:
            if pattern.search(message):
                error_type = etype
                layer = elayer
                break

        signature = self.generate_error_signature(error_type, message, origin)
        return ClassifiedError(
            error_type=error_type,
            layer=layer,
            message=message,
            signature=signature,
            origin=origin,
            payload=dict(payload or {}),
        )

    def map_error_to_layer(self, error_type: ErrorType) -> ErrorLayer:
        mapping = {
            ErrorType.CONTRACT_VIOLATION: ErrorLayer.CONTRACTS,
            ErrorType.DATA_DRIFT: ErrorLayer.DATA,
            ErrorType.SNAPSHOT_MISMATCH: ErrorLayer.SNAPSHOT,
            ErrorType.EVOLUTION_BREAKING: ErrorLayer.EVOLUTION,
            ErrorType.CI_FAILURE: ErrorLayer.CI,
            ErrorType.SYSTEM_LOCK_VIOLATION: ErrorLayer.SYSTEM_LOCK,
            ErrorType.CONFIG_DRIFT: ErrorLayer.CONFIG,
            ErrorType.RUNTIME_MUTATION: ErrorLayer.RUNTIME,
        }
        return mapping.get(error_type, ErrorLayer.UNKNOWN)

    @staticmethod
    def generate_error_signature(
        error_type: ErrorType,
        message: str,
        origin: str,
    ) -> str:
        body = json.dumps(
            {
                "error_type": error_type.value,
                "message": message.strip(),
                "origin": origin,
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        return hashlib.sha256(body.encode("utf-8")).hexdigest()

    def classify_gate_failures(
        self,
        gate_reports: dict[str, dict[str, Any]],
    ) -> list[ClassifiedError]:
        classified: list[ClassifiedError] = []
        for gate, report in sorted(gate_reports.items()):
            if report.get("status") != "FAIL":
                continue
            for failure in report.get("failures", []):
                classified.append(
                    self.classify_error(
                        failure,
                        origin=gate,
                        payload={"gate": gate},
                    )
                )
        return classified
