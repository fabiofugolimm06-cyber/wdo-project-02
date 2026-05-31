"""
config_validator.py — validação de schema de config.
"""

from __future__ import annotations

from typing import Any

from src.config.config_contract import ConfigContract


class ConfigValidator:
    """Valida contratos de config contra regras estruturais."""

    _REQUIRED_TOP_KEYS = frozenset({"config_id", "environment", "determinism", "pipeline"})

    def validate(self, contract: ConfigContract) -> dict[str, Any]:
        failures: list[str] = []
        schema = contract.schema

        missing = self._REQUIRED_TOP_KEYS - frozenset(schema.keys())
        if missing:
            failures.append(f"schema: chaves ausentes {sorted(missing)}.")

        det = schema.get("determinism", {})
        if not isinstance(det, dict):
            failures.append("determinism: deve ser dict.")
        elif "seed" not in det:
            failures.append("determinism.seed obrigatório.")

        if schema.get("config_id") != contract.config_id:
            failures.append("schema.config_id diverge de config_id.")

        if len(contract.hash) != 64:
            failures.append("hash deve ser SHA256 hex (64 chars).")

        ordered = sorted(failures)
        return {
            "status": "PASS" if not ordered else "FAIL",
            "failures": ordered,
        }

    def validate_active_matches_canonical(
        self,
        contract: ConfigContract,
        *,
        environment: str = "ci",
    ) -> dict[str, Any]:
        from src.config.config_contract import build_canonical_config_schema, compute_config_hash

        canonical = build_canonical_config_schema(environment=environment)
        failures: list[str] = []
        if compute_config_hash(canonical) != contract.hash:
            failures.append("config ativa diverge do schema canônico (drift detectado).")
        base = self.validate(contract)
        failures.extend(base["failures"])
        ordered = sorted(failures)
        return {
            "status": "PASS" if not ordered else "FAIL",
            "failures": ordered,
        }
