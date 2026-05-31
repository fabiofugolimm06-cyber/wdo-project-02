"""
config_freeze_engine.py — congelamento e enforcement de config ativa.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.config.config_contract import WDO_ACTIVE_CONFIG_ID, ConfigContract
from src.config.config_registry import ConfigRegistry, bootstrap_production_config_registry
from src.config.config_validator import ConfigValidator


@dataclass
class ConfigFreezeEngine:
    """
    Freeze de config ativa por ambiente.

    Alteração exige nova versão + aprovação CI (registry append).
    """

    registry: ConfigRegistry = field(default_factory=bootstrap_production_config_registry)
    _frozen_hash: str | None = field(default=None, init=False)
    _environment: str = "ci"

    def freeze_active_config(self, *, environment: str = "ci") -> ConfigContract:
        self._environment = environment
        self.registry = bootstrap_production_config_registry(environment=environment)
        active = self.registry.get_config(WDO_ACTIVE_CONFIG_ID)
        validation = ConfigValidator().validate_active_matches_canonical(
            active,
            environment=environment,
        )
        if validation["status"] == "FAIL":
            raise RuntimeError(
                "freeze_active_config falhou: " + "; ".join(validation["failures"])
            )
        self._frozen_hash = active.hash
        return active

    def enforce_config_lock(self) -> dict[str, Any]:
        failures: list[str] = []
        integrity = self.registry.validate_config_integrity()
        if not integrity["valid"]:
            failures.extend(integrity["errors"])

        if self._frozen_hash is None:
            self.freeze_active_config(environment=self._environment)

        active = self.registry.get_config(WDO_ACTIVE_CONFIG_ID)
        if not active.locked:
            failures.append("config ativa deve estar locked=True.")

        if self._frozen_hash and active.hash != self._frozen_hash:
            failures.append(
                "config freeze violado: hash ativo diverge do freeze baseline."
            )

        validator = ConfigValidator().validate_active_matches_canonical(
            active,
            environment=self._environment,
        )
        if validator["status"] == "FAIL":
            failures.extend(validator["failures"])

        ordered = sorted(failures)
        return {
            "status": "PASS" if not ordered else "FAIL",
            "failures": ordered,
            "frozen_hash": self._frozen_hash,
        }

    def block_unregistered_changes(
        self,
        proposed: ConfigContract,
    ) -> dict[str, Any]:
        failures: list[str] = []
        key = proposed.registry_key

        try:
            existing = self.registry.get_config(proposed.config_id, proposed.version)
            if existing.hash != proposed.hash:
                failures.append(
                    f"{key}: overwrite proibido (hash diverge)."
                )
        except Exception:
            if proposed.version == "v1" and self.registry.list_configs(proposed.config_id):
                failures.append(
                    f"{key}: alteração exige nova versão (v2+)."
                )

        validation = ConfigValidator().validate(proposed)
        if validation["status"] == "FAIL":
            failures.extend(validation["failures"])

        ordered = sorted(failures)
        return {
            "status": "PASS" if not ordered else "FAIL",
            "failures": ordered,
        }


def run_config_freeze_gate(*, environment: str = "ci") -> dict[str, Any]:
    """Gate CI — config-freeze-gate."""
    engine = ConfigFreezeEngine()
    engine.freeze_active_config(environment=environment)
    return engine.enforce_config_lock()
