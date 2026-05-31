"""
migration_engine.py — plano explícito de migração v1→v2 com rollback.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Mapping

from src.evolution.breaking_change_detector import detect_contract_breaking_changes
from src.evolution.evolution_registry import EvolutionRegistry
from src.evolution.schema_version import SchemaVersion


class MigrationError(Exception):
    """Erro de planejamento ou execução de migração."""


@dataclass(frozen=True)
class MigrationStep:
    """Passo explícito de migração (nunca silencioso)."""

    action: str
    path: str
    params: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "path": self.path,
            "params": dict(self.params),
        }


@dataclass(frozen=True)
class MigrationPlan:
    contract_id: str
    from_version: str
    to_version: str
    steps: tuple[MigrationStep, ...]
    rollback_steps: tuple[MigrationStep, ...]
    backward_compatible: bool
    breaking: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_id": self.contract_id,
            "from_version": self.from_version,
            "to_version": self.to_version,
            "steps": [s.to_dict() for s in self.steps],
            "rollback_steps": [s.to_dict() for s in self.rollback_steps],
            "backward_compatible": self.backward_compatible,
            "breaking": self.breaking,
        }


class MigrationEngine:
    """
    Engine de migração controlada entre ``SchemaVersion``.

    Breaking change exige nova versão + plano explícito; rollback suportado.
    """

    def plan_migration(
        self,
        v1: SchemaVersion,
        v2: SchemaVersion,
        *,
        explicit_steps: tuple[MigrationStep, ...] | None = None,
    ) -> MigrationPlan:
        if v1.contract_id != v2.contract_id:
            raise MigrationError(
                f"plan_migration: contract_id diverge "
                f"({v1.contract_id!r} vs {v2.contract_id!r})."
            )
        if v1.version == v2.version and v1.hash == v2.hash:
            return MigrationPlan(
                contract_id=v1.contract_id,
                from_version=v1.version,
                to_version=v2.version,
                steps=(),
                rollback_steps=(),
                backward_compatible=True,
                breaking=False,
            )
        if v2.parent_version is not None and v2.parent_version != v1.version:
            raise MigrationError(
                f"plan_migration: parent_version de v2 ({v2.parent_version!r}) "
                f"deve apontar para v1 ({v1.version!r})."
            )

        diff = detect_contract_breaking_changes(v1.schema, v2.schema)
        breaking = diff["breaking"]

        if breaking:
            if explicit_steps is None:
                raise MigrationError(
                    "plan_migration: breaking change exige steps explícitos "
                    "(migração não pode ser automática silenciosa)."
                )
            steps = list(explicit_steps)
        elif explicit_steps is not None:
            steps = list(explicit_steps)
        else:
            steps = self._auto_steps(v1.schema, v2.schema, diff["changes"])

        rollback_steps = self._build_rollback(steps)
        backward_compatible = not breaking and all(
            s.action in {"add_field", "noop", "copy_block"} for s in steps
        )

        if breaking and not steps:
            raise MigrationError(
                "plan_migration: breaking change exige steps explícitos."
            )

        return MigrationPlan(
            contract_id=v1.contract_id,
            from_version=v1.version,
            to_version=v2.version,
            steps=tuple(steps),
            rollback_steps=tuple(rollback_steps),
            backward_compatible=backward_compatible,
            breaking=breaking,
        )

    def validate_migration_path(
        self,
        registry: EvolutionRegistry,
        contract_id: str,
        from_version: str,
        to_version: str,
    ) -> dict[str, Any]:
        """Valida cadeia parent imutável entre versões."""
        failures: list[str] = []

        try:
            current = registry.get_version(contract_id, to_version)
        except Exception as exc:  # noqa: BLE001
            return {"valid": False, "failures": [str(exc)]}

        path: list[str] = [current.version]
        while current.version != from_version:
            if current.parent_version is None:
                failures.append(
                    f"cadeia quebrada: {from_version!r} não é ancestral de "
                    f"{to_version!r}."
                )
                break
            try:
                current = registry.get_version(contract_id, current.parent_version)
            except Exception as exc:  # noqa: BLE001
                failures.append(f"parent ausente: {exc}.")
                break
            if current.version in path:
                failures.append("ciclo detectado na cadeia de versões.")
                break
            path.append(current.version)
        else:
            path = list(reversed(path))

        if path and path[0] != from_version:
            failures.append(
                f"path inválido: esperado início {from_version!r}, got {path!r}."
            )

        return {
            "valid": not failures,
            "path": path,
            "failures": sorted(failures),
        }

    def execute_migration_plan(
        self,
        data: Mapping[str, Any],
        plan: MigrationPlan,
    ) -> dict[str, Any]:
        """Executa plano forward (explícito)."""
        result = copy.deepcopy(dict(data))
        for step in plan.steps:
            result = self._apply_step(result, step)
        return result

    def rollback_migration(
        self,
        data: Mapping[str, Any],
        plan: MigrationPlan,
    ) -> dict[str, Any]:
        """Rollback via ``rollback_steps`` (ordem explícita)."""
        result = copy.deepcopy(dict(data))
        for step in plan.rollback_steps:
            result = self._apply_step(result, step)
        return result

    @staticmethod
    def _auto_steps(
        old: Mapping[str, Any],
        new: Mapping[str, Any],
        changes: list[str],
    ) -> list[MigrationStep]:
        steps: list[MigrationStep] = []

        old_top = frozenset(old.get("required_top_keys", []))
        new_top = frozenset(new.get("required_top_keys", []))
        for key in sorted(new_top - old_top):
            steps.append(
                MigrationStep(
                    action="add_field",
                    path=key,
                    params={"default": None, "explicit": True},
                )
            )
        # Remoções são breaking — nunca auto-geradas (exigem explicit_steps).

        return steps

    @staticmethod
    def _build_rollback(steps: list[MigrationStep]) -> list[MigrationStep]:
        rollback: list[MigrationStep] = []
        for step in reversed(steps):
            if step.action == "add_field":
                rollback.append(
                    MigrationStep(
                        action="remove_field",
                        path=step.path,
                        params={"rollback": True},
                    )
                )
            elif step.action == "remove_field":
                rollback.append(
                    MigrationStep(
                        action="add_field",
                        path=step.path,
                        params={
                            "default": step.params.get("previous_value"),
                            "rollback": True,
                        },
                    )
                )
            elif step.action == "rename_field":
                rollback.append(
                    MigrationStep(
                        action="rename_field",
                        path=step.path,
                        params={
                            "from": step.params.get("to"),
                            "to": step.params.get("from"),
                            "rollback": True,
                        },
                    )
                )
        return rollback

    @staticmethod
    def _apply_step(data: dict[str, Any], step: MigrationStep) -> dict[str, Any]:
        if step.action == "noop":
            return data
        if step.action == "copy_block":
            return data

        if "." in step.path:
            block, key = step.path.split(".", 1)
            block_data = data.setdefault(block, {})
            if not isinstance(block_data, dict):
                raise MigrationError(
                    f"execute: bloco {block!r} deve ser dict para {step.path!r}."
                )
            target = block_data
            field = key
        else:
            target = data
            field = step.path

        if step.action == "add_field":
            if field not in target:
                target[field] = step.params.get("default")
        elif step.action == "remove_field":
            target.pop(field, None)
        elif step.action == "rename_field":
            src = step.params.get("from", field)
            dst = step.params.get("to")
            if dst is None:
                raise MigrationError(f"rename_field sem 'to': {step}.")
            if src in target:
                target[dst] = target.pop(src)
        else:
            raise MigrationError(f"ação desconhecida: {step.action!r}.")

        return data
