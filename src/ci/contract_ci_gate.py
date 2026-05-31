"""
contract_ci_gate.py — CI gate para Contract Registry central.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from microstructure.contracts.contract_models import PipelineContract
from microstructure.contracts.registry import (
    CONTRACT_TYPES,
    ContractRegistry,
    contract_registry,
    get_contract,
)
from microstructure.contracts.schema_diff import diff_contracts

_BASELINES_DIR = (
    Path(__file__).resolve().parents[2]
    / "microstructure"
    / "contracts"
    / "baselines"
)

_REQUIRED_REGISTRY_KEYS: tuple[str, ...] = ("ml_pipeline:v1", "full_pipeline:v1")


def _ci_report(failures: list[str]) -> dict[str, Any]:
    """Relatório determinístico — failures sempre ordenadas."""
    ordered = sorted(failures)
    return {
        "status": "PASS" if not ordered else "FAIL",
        "failures": ordered,
    }


def _contract_content_hash(contract: PipelineContract) -> str:
    payload = json.dumps(
        contract.to_dict(),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _load_baseline_contract(name: str) -> PipelineContract:
    path = _BASELINES_DIR / f"{name}.json"
    if not path.is_file():
        raise FileNotFoundError(f"baseline ausente: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    return PipelineContract.from_dict(data)


class ContractCIGate:
    """
    Architecture gatekeeper para contratos de pipeline versionados.

    FAIL bloqueia execução downstream (contrato inválido, drift breaking,
    registry inconsistente ou dependência ausente).
    """

    def validate_contract(self, contract: PipelineContract) -> bool:
        """
        Valida um contrato isolado (schema + hash interno).

        Returns
        -------
        bool
            True se válido; False se inválido (sem exceção).
        """
        failures: list[str] = []
        failures.extend(self._collect_contract_failures(contract))
        return len(failures) == 0

    def validate_registry(self, registry: ContractRegistry) -> dict[str, Any]:
        """Valida integridade do Contract Registry."""
        failures: list[str] = []

        if not registry.is_frozen:
            failures.append("registry: deve estar frozen após bootstrap.")

        registered = set(registry.list_contracts())
        for key in _REQUIRED_REGISTRY_KEYS:
            if key not in registered:
                failures.append(f"registry: dependência ausente {key!r}.")

        for contract_type in CONTRACT_TYPES:
            try:
                registry.get_active_version(contract_type)
            except Exception as exc:  # noqa: BLE001
                failures.append(
                    f"registry: versão ativa ausente para {contract_type!r} — {exc}."
                )

        seen_ids: set[str] = set()
        for key in sorted(registry.list_contracts()):
            contract = registry.get_contract(key)
            if contract.contract_id in seen_ids:
                failures.append(
                    f"registry: contract_id duplicado {contract.contract_id!r}."
                )
            seen_ids.add(contract.contract_id)
            failures.extend(
                f"{key}: {msg}" for msg in self._collect_contract_failures(contract)
            )

        return _ci_report(failures)

    def run_full_contract_check(
        self,
        registry: ContractRegistry | None = None,
    ) -> dict[str, Any]:
        """
        Check completo: registry + baselines CI + dependências cruzadas.
        """
        reg = registry or contract_registry
        failures: list[str] = []

        registry_report = self.validate_registry(reg)
        failures.extend(registry_report["failures"])

        baseline_pairs = (
            ("ml_pipeline_contract_v1", "ml_pipeline:v1"),
            ("full_pipeline_contract_v1", "full_pipeline:v1"),
        )
        for baseline_name, registry_key in baseline_pairs:
            try:
                baseline = _load_baseline_contract(baseline_name)
                current = reg.get_contract(registry_key)
            except Exception as exc:  # noqa: BLE001
                failures.append(
                    f"baseline:{baseline_name}: falha ao carregar — {exc}."
                )
                continue

            diff = diff_contracts(baseline, current)
            if diff.breaking_changes:
                failures.append(
                    f"baseline:{baseline_name}: breaking change detectado "
                    f"(removed={sorted(diff.removed_keys)}, "
                    f"modified={list(diff.modified_constraints)})."
                )

            if _contract_content_hash(baseline) != _contract_content_hash(current):
                if not diff.breaking_changes:
                    failures.append(
                        f"baseline:{baseline_name}: hash diverge sem diff breaking "
                        f"(revisar baseline ou bump de versão)."
                    )

        failures.extend(self._validate_cross_contract_dependencies(reg))

        return _ci_report(failures)

    @staticmethod
    def _collect_contract_failures(contract: PipelineContract) -> list[str]:
        failures: list[str] = []
        if not contract.contract_id.strip():
            failures.append("contract_id vazio.")
        if not contract.version.strip():
            failures.append("version vazia.")
        if not contract.required_top_keys:
            failures.append("required_top_keys vazio.")
        if not contract.output_schema:
            failures.append("output_schema vazio.")

        try:
            recomputed = PipelineContract.from_dict(contract.to_dict())
        except Exception as exc:  # noqa: BLE001
            failures.append(f"schema inválido — {exc}.")
            return failures

        if _contract_content_hash(recomputed) != _contract_content_hash(contract):
            failures.append("hash de conteúdo inconsistente após round-trip.")

        return failures

    @staticmethod
    def _validate_cross_contract_dependencies(
        registry: ContractRegistry,
    ) -> list[str]:
        failures: list[str] = []
        try:
            ml = registry.get_contract("ml_pipeline:v1")
            full = registry.get_contract("full_pipeline:v1")
        except Exception as exc:  # noqa: BLE001
            return [f"dependência cruzada: {exc}."]

        ml_metrics = next(
            (n for n in ml.nested_schemas if n.block_name == "metrics"),
            None,
        )
        full_model = next(
            (n for n in full.nested_schemas if n.block_name == "model_metrics"),
            None,
        )
        if ml_metrics is None:
            failures.append("ml_pipeline:v1: bloco metrics ausente.")
        if full_model is None:
            failures.append("full_pipeline:v1: bloco model_metrics ausente.")
        if ml_metrics and full_model:
            if ml_metrics.required_keys != full_model.required_keys:
                failures.append(
                    "dependência: model_metrics.required_keys diverge de "
                    "ml_pipeline.metrics.required_keys."
                )
            if ml_metrics.forbidden_keys != full_model.forbidden_keys:
                failures.append(
                    "dependência: model_metrics.forbidden_keys diverge de "
                    "ml_pipeline.metrics.forbidden_keys."
                )

        if "model_metrics" not in full.required_top_keys:
            failures.append(
                "full_pipeline:v1: model_metrics ausente em required_top_keys."
            )

        return failures


def validate_contract_output(
    contract_id: str,
    output: Mapping[str, Any],
) -> dict[str, Any]:
    """Atalho CI — valida output runtime contra contrato do registry."""
    failures: list[str] = []
    try:
        contract = get_contract(contract_id)
        contract.validate_output(output)
    except Exception as exc:  # noqa: BLE001
        failures.append(f"{contract_id}: {exc}.")
    return _ci_report(failures)
