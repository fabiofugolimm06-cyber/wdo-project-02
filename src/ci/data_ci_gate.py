"""
data_ci_gate.py — CI gate para Data Contract Layer v1.
"""

from __future__ import annotations

from typing import Any, Mapping

import pandas as pd

from src.contracts.data.data_contract import (
    OHLCV_SCHEMA_V1,
    DataContract,
)
from src.contracts.data.dataset_fingerprint import (
    generate_fingerprint,
    generate_schema_hash,
)
from src.contracts.data.dataset_registry import DatasetRegistry

_FINGERPRINT_STABILITY_RUNS = 20

# Datasets canônicos alinhados aos snapshots de pipeline (seed 42).
_CANONICAL_DATASETS: tuple[tuple[str, int, str], ...] = (
    ("wdo_ml_snapshot", 200, "v1"),
    ("wdo_e2e_snapshot", 300, "v1"),
)


def build_canonical_dataset_registry() -> tuple[DatasetRegistry, dict[str, pd.DataFrame]]:
    """
    Registry bootstrap para CI — datasets OHLCV determinísticos (seed 42).

    Returns
    -------
    (registry, data_by_key) para ``run_full_data_check``.
    """
    from microstructure.determinism import WDO_PROJECT_RANDOM_SEED
    from tests.ohlcv_data import make_ohlcv

    registry = DatasetRegistry()
    data_by_key: dict[str, pd.DataFrame] = {}

    for dataset_id, n_bars, version in _CANONICAL_DATASETS:
        df = make_ohlcv(n_bars, seed=WDO_PROJECT_RANDOM_SEED)
        contract = DataContract.from_dataframe(
            df,
            dataset_id=dataset_id,
            symbol="WDO",
            timeframe="1min",
            source="tests.make_ohlcv",
            version=version,
        )
        registry.register(contract)
        data_by_key[contract.registry_key] = df

    return registry, data_by_key


def _ci_report(failures: list[str]) -> dict[str, Any]:
    ordered = sorted(failures)
    return {
        "status": "PASS" if not ordered else "FAIL",
        "failures": ordered,
    }


class DataCIGate:
    """
    CI gate para datasets OHLCV versionados.

    FAIL em fingerprint instável, duplicação, schema drift ou registry corrupto.
    """

    def validate_dataset_contract(
        self,
        data_contract: DataContract,
        *,
        reference_schema: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Valida integridade de um ``DataContract`` isolado."""
        failures: list[str] = []
        ref = dict(reference_schema or OHLCV_SCHEMA_V1)

        if not data_contract.dataset_id.strip():
            failures.append("dataset_id vazio.")
        if not data_contract.version.strip():
            failures.append("version vazia.")
        if len(data_contract.fingerprint) != 64:
            failures.append("fingerprint deve ser SHA256 hex (64 chars).")
        if len(data_contract.dataset_hash) != 64:
            failures.append("dataset_hash deve ser SHA256 hex (64 chars).")
        if len(data_contract.schema_hash) != 64:
            failures.append("schema_hash deve ser SHA256 hex (64 chars).")

        try:
            recomputed_schema_hash = generate_schema_hash(data_contract.schema)
        except Exception as exc:  # noqa: BLE001
            failures.append(f"schema inválido — {exc}.")
            recomputed_schema_hash = None

        if (
            recomputed_schema_hash is not None
            and recomputed_schema_hash != data_contract.schema_hash
        ):
            failures.append("schema_hash inconsistente com schema.")

        drift_failures = self._detect_schema_drift(data_contract.schema, ref)
        failures.extend(drift_failures)

        return _ci_report(failures)

    def validate_fingerprint_stability(
        self,
        data_contract: DataContract,
        data: pd.DataFrame | None = None,
        *,
        runs: int = _FINGERPRINT_STABILITY_RUNS,
    ) -> dict[str, Any]:
        """
        Garante fingerprint imutável em ``runs`` recálculos.

        Com ``data``, valida ``generate_fingerprint``; sem ``data``, valida
        ``schema_hash`` e campos hash do contrato.
        """
        failures: list[str] = []

        if data is not None:
            fingerprints: set[str] = set()
            for _ in range(runs):
                fp = generate_fingerprint(
                    data,
                    data_contract.schema,
                    normalization_version=data_contract.normalization_version,
                )
                fingerprints.add(fp)
            if len(fingerprints) != 1:
                failures.append(
                    f"fingerprint instável em {runs} runs "
                    f"({len(fingerprints)} valores distintos)."
                )
            elif next(iter(fingerprints)) != data_contract.fingerprint:
                failures.append(
                    "fingerprint do contrato diverge do recalculado."
                )
            try:
                data_contract.verify_against_data(data)
            except Exception as exc:  # noqa: BLE001
                failures.append(f"verify_against_data falhou — {exc}.")
        else:
            schema_hashes: set[str] = set()
            for _ in range(runs):
                schema_hashes.add(generate_schema_hash(data_contract.schema))
            if len(schema_hashes) != 1:
                failures.append(
                    f"schema_hash instável em {runs} runs."
                )
            elif next(iter(schema_hashes)) != data_contract.schema_hash:
                failures.append("schema_hash do contrato diverge do recalculado.")

        return _ci_report(failures)

    def validate_registry_integrity(
        self,
        dataset_registry: DatasetRegistry,
        *,
        reference_schema: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Valida registry + contratos registrados (sem bypass)."""
        failures: list[str] = []
        report = dataset_registry.validate_integrity()
        if not report.get("valid", False):
            for err in report.get("errors", []):
                failures.append(f"registry: {err}")

        contracts = dataset_registry.list()
        fingerprints: set[str] = set()
        for contract in contracts:
            if contract.fingerprint in fingerprints:
                failures.append(
                    f"registry: fingerprint duplicado {contract.fingerprint!r}."
                )
            fingerprints.add(contract.fingerprint)

            contract_report = self.validate_dataset_contract(
                contract,
                reference_schema=reference_schema,
            )
            failures.extend(
                f"{contract.registry_key}: {msg}"
                for msg in contract_report["failures"]
            )

        if not contracts:
            failures.append("registry: nenhum dataset registrado.")

        return _ci_report(failures)

    def run_full_data_check(
        self,
        dataset_registry: DatasetRegistry | None = None,
        data_by_key: dict[str, pd.DataFrame] | None = None,
    ) -> dict[str, Any]:
        """Agrega validação de contratos + registry + estabilidade opcional."""
        if dataset_registry is None:
            dataset_registry, data_by_key = build_canonical_dataset_registry()
        failures: list[str] = []
        registry_report = self.validate_registry_integrity(dataset_registry)
        failures.extend(registry_report["failures"])

        data_by_key = data_by_key or {}
        for contract in dataset_registry.list():
            df = data_by_key.get(contract.registry_key)
            if df is not None:
                stability = self.validate_fingerprint_stability(contract, df)
                failures.extend(
                    f"{contract.registry_key}: {msg}"
                    for msg in stability["failures"]
                )

        return _ci_report(failures)

    @staticmethod
    def _detect_schema_drift(
        schema: Mapping[str, Any],
        reference: Mapping[str, Any],
    ) -> list[str]:
        failures: list[str] = []
        ref_props = reference.get("properties", {})
        cur_props = schema.get("properties", {})

        for key in ("columns", "index"):
            ref_block = ref_props.get(key)
            cur_block = cur_props.get(key)
            if ref_block is None:
                continue
            if cur_block != ref_block:
                failures.append(f"schema drift em properties.{key}.")

        ref_required = reference.get("required")
        cur_required = schema.get("required")
        if ref_required and cur_required != ref_required:
            failures.append(
                f"schema drift em required: {cur_required} != {ref_required}."
            )

        return failures
