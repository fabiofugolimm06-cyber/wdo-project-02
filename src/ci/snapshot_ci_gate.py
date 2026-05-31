"""
snapshot_ci_gate.py — CI gate para snapshots de pipeline e determinismo.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from microstructure.contracts import get_contract
from microstructure.contracts.snapshot import (
    DEFAULT_NUMERIC_EPSILON,
    build_full_pipeline_snapshot,
    build_ml_pipeline_snapshot,
    compare_pipeline_snapshots,
    load_snapshot,
)
from microstructure.determinism import WDO_PROJECT_RANDOM_SEED, set_global_determinism
from microstructure.model.pipeline import pipeline_fingerprint, run_ml_pipeline_v1
from microstructure.pipeline.end_to_end import run_full_pipeline
from tests.ohlcv_data import make_ohlcv

_SNAPSHOTS_DIR = Path(__file__).resolve().parents[2] / "tests" / "snapshots"
_ML_SNAPSHOT_PATH = _SNAPSHOTS_DIR / "ml_pipeline_v1_seed42.json"
_E2E_SNAPSHOT_PATH = _SNAPSHOTS_DIR / "full_pipeline_v1_seed42.json"

_REQUIRED_SNAPSHOT_KEYS: tuple[str, ...] = (
    "contract_id",
    "contract_version",
    "schema",
    "structure",
)

_DEFAULT_ML_BARS = 200
_DEFAULT_E2E_BARS = 300


def _ci_report(failures: list[str]) -> dict[str, Any]:
    ordered = sorted(failures)
    return {
        "status": "PASS" if not ordered else "FAIL",
        "failures": ordered,
    }


class SnapshotCIGate:
    """
    CI gate para snapshots estruturais e determinismo de pipeline.

    FAIL em drift de schema, drift numérico > epsilon ou runs não idênticos.
    """

    def __init__(
        self,
        *,
        epsilon: float = DEFAULT_NUMERIC_EPSILON,
        seed: int = WDO_PROJECT_RANDOM_SEED,
    ) -> None:
        self.epsilon = epsilon
        self.seed = seed

    def validate_snapshot(self, snapshot: Mapping[str, Any]) -> dict[str, Any]:
        """Valida shape mínimo de um snapshot de pipeline."""
        failures: list[str] = []

        for key in _REQUIRED_SNAPSHOT_KEYS:
            if key not in snapshot:
                failures.append(f"snapshot: chave obrigatória ausente {key!r}.")

        schema = snapshot.get("schema")
        structure = snapshot.get("structure")
        if not isinstance(schema, dict):
            failures.append("snapshot: schema deve ser dict.")
        if not isinstance(structure, dict):
            failures.append("snapshot: structure deve ser dict.")

        contract_id = snapshot.get("contract_id")
        if contract_id:
            try:
                get_contract(str(contract_id))
            except Exception as exc:  # noqa: BLE001
                failures.append(
                    f"snapshot: contract_id {contract_id!r} ausente no registry — {exc}."
                )

        numeric_blocks = (
            "metrics",
            "model_metrics",
            "execution_metrics",
            "backtest_metrics",
        )
        if not any(block in snapshot for block in numeric_blocks):
            failures.append(
                "snapshot: nenhum bloco numérico conhecido "
                f"({', '.join(numeric_blocks)})."
            )

        return _ci_report(failures)

    def compare_with_previous(
        self,
        snapshot: Mapping[str, Any],
        previous: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Compara snapshot atual vs referência (schema estrito + epsilon numérico)."""
        errors = compare_pipeline_snapshots(
            snapshot,
            previous,
            epsilon=self.epsilon,
        )
        return _ci_report(errors)

    def enforce_determinism(
        self,
        *,
        pipeline: str = "ml",
        snapshot_runs: int = 20,
    ) -> dict[str, Any]:
        """
        Executa pipeline ``snapshot_runs`` vezes — outputs devem ser idênticos.

        ``pipeline``: ``"ml"`` | ``"full"``.
        """
        failures: list[str] = []
        if snapshot_runs < 1:
            failures.append("snapshot_runs deve ser >= 1.")
            return _ci_report(failures)

        if pipeline == "ml":
            runner = self._run_ml_pipeline_output
            use_pipeline_fp = True
        elif pipeline == "full":
            runner = self._run_e2e_pipeline_output
            use_pipeline_fp = False
        else:
            failures.append(f"pipeline desconhecido {pipeline!r}.")
            return _ci_report(failures)

        contract = get_contract(
            "ml_pipeline:v1" if pipeline == "ml" else "full_pipeline:v1"
        )
        base_snapshot: dict[str, Any] | None = None
        base_fp: tuple[Any, ...] | str | None = None

        for run_idx in range(snapshot_runs):
            set_global_determinism(self.seed)
            output = runner()
            if pipeline == "ml":
                current = build_ml_pipeline_snapshot(
                    output,
                    contract_id=contract.contract_id,
                    contract_version=contract.version,
                )
            else:
                current = build_full_pipeline_snapshot(
                    output,
                    contract_id=contract.contract_id,
                    contract_version=contract.version,
                )

            validation = self.validate_snapshot(current)
            if validation["status"] == "FAIL":
                failures.extend(
                    f"run {run_idx + 1}: {msg}" for msg in validation["failures"]
                )
                continue

            if use_pipeline_fp:
                fp: tuple[Any, ...] | str = pipeline_fingerprint(output)
            else:
                fp = self._e2e_fingerprint(current)

            if base_snapshot is None:
                base_snapshot = current
                base_fp = fp
            else:
                if fp != base_fp:
                    failures.append(
                        f"run {run_idx + 1}: fingerprint divergiu de run 1."
                    )
                drift = compare_pipeline_snapshots(
                    current,
                    base_snapshot,
                    epsilon=self.epsilon,
                )
                for err in drift:
                    failures.append(f"run {run_idx + 1}: {err}")

        return _ci_report(failures)

    def run_full_snapshot_check(
        self,
        *,
        snapshot_runs: int = 20,
    ) -> dict[str, Any]:
        """Delega ao Snapshot-as-Spec Engine (spec enforcement layer)."""
        from src.snapshot_spec.snapshot_ci_gate import SnapshotCIGate as SnapshotSpecCIGate

        return SnapshotSpecCIGate(
            seed=self.seed,
            snapshot_runs=snapshot_runs,
        ).run_full_snapshot_spec_check()

    def _run_ml_pipeline_output(self) -> dict[str, Any]:
        return run_ml_pipeline_v1(
            make_ohlcv(_DEFAULT_ML_BARS, seed=self.seed),
            seed=self.seed,
        )

    def _run_e2e_pipeline_output(self) -> dict[str, Any]:
        return run_full_pipeline(
            make_ohlcv(_DEFAULT_E2E_BARS, seed=self.seed),
            price_col="fechamento",
        )

    def _run_ml_snapshot(self) -> dict[str, Any]:
        contract = get_contract("ml_pipeline:v1")
        out = self._run_ml_pipeline_output()
        return build_ml_pipeline_snapshot(
            out,
            contract_id=contract.contract_id,
            contract_version=contract.version,
        )

    def _run_e2e_snapshot(self) -> dict[str, Any]:
        contract = get_contract("full_pipeline:v1")
        out = self._run_e2e_pipeline_output()
        return build_full_pipeline_snapshot(
            out,
            contract_id=contract.contract_id,
            contract_version=contract.version,
        )

    @staticmethod
    def _e2e_fingerprint(snapshot: Mapping[str, Any]) -> str:
        import hashlib
        import json

        payload = json.dumps(
            snapshot,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            default=str,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
