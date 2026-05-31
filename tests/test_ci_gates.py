"""
tests/test_ci_gates.py — integração CI Engine + Contract/Data/Snapshot gates.
"""

from __future__ import annotations

import copy

import pandas as pd
import pytest

from microstructure.contracts import ml_pipeline_contract_v1
from microstructure.contracts.registry import contract_registry
from microstructure.contracts.snapshot import load_snapshot
from src.ci import ContractCIGate, DataCIGate, SnapshotCIGate
from src.contracts.data import DataContract, DatasetRegistry, OHLCV_SCHEMA_V1
from tests.ohlcv_data import make_ohlcv

_SNAPSHOTS = (
    __import__("pathlib").Path(__file__).resolve().parent / "snapshots"
)


class TestContractCIGate:
    def test_validate_contract_passes_v1(self):
        gate = ContractCIGate()
        assert gate.validate_contract(ml_pipeline_contract_v1) is True

    def test_validate_registry_passes_global(self):
        gate = ContractCIGate()
        report = gate.validate_registry(contract_registry)
        assert report["status"] == "PASS"
        assert report["failures"] == []

    def test_run_full_contract_check_passes(self):
        gate = ContractCIGate()
        report = gate.run_full_contract_check()
        assert report["status"] == "PASS", report["failures"]

    def test_validate_contract_fails_on_empty_id(self):
        gate = ContractCIGate()
        broken = copy.deepcopy(ml_pipeline_contract_v1)
        object.__setattr__(broken, "contract_id", "")
        assert gate.validate_contract(broken) is False


class TestDataCIGate:
    @pytest.fixture
    def df(self) -> pd.DataFrame:
        return make_ohlcv(n=200, seed=42)

    @pytest.fixture
    def registry(self, df: pd.DataFrame) -> DatasetRegistry:
        reg = DatasetRegistry()
        reg.register(
            DataContract.from_dataframe(
                df,
                dataset_id="wdo_synthetic",
                symbol="WDO",
                timeframe="1min",
                source="tests.make_ohlcv",
                version="v1",
            )
        )
        return reg

    def test_validate_dataset_contract_passes(self, df: pd.DataFrame):
        contract = DataContract.from_dataframe(
            df,
            dataset_id="wdo_synthetic",
            symbol="WDO",
            timeframe="1min",
            source="tests.make_ohlcv",
            version="v1",
        )
        report = DataCIGate().validate_dataset_contract(contract)
        assert report["status"] == "PASS"

    def test_validate_fingerprint_stability_20_runs(self, df: pd.DataFrame):
        contract = DataContract.from_dataframe(
            df,
            dataset_id="wdo_synthetic",
            symbol="WDO",
            timeframe="1min",
            source="tests.make_ohlcv",
            version="v1",
        )
        report = DataCIGate().validate_fingerprint_stability(contract, df, runs=20)
        assert report["status"] == "PASS", report["failures"]

    def test_validate_registry_integrity_passes(self, registry: DatasetRegistry):
        report = DataCIGate().validate_registry_integrity(registry)
        assert report["status"] == "PASS", report["failures"]

    def test_run_full_data_check_default_registry(self):
        report = DataCIGate().run_full_data_check()
        assert report["status"] == "PASS", report["failures"]

    def test_schema_drift_fails(self, df: pd.DataFrame):
        drifted_schema = dict(OHLCV_SCHEMA_V1)
        drifted_schema["properties"] = dict(drifted_schema["properties"])
        drifted_schema["properties"]["index"] = {"type": "string", "const": "int64"}
        contract = DataContract.from_dataframe(
            df,
            dataset_id="wdo_synthetic",
            symbol="WDO",
            timeframe="1min",
            source="tests.make_ohlcv",
            version="v1",
            schema=drifted_schema,
        )
        report = DataCIGate().validate_dataset_contract(
            contract,
            reference_schema=OHLCV_SCHEMA_V1,
        )
        assert report["status"] == "FAIL"
        assert any("schema drift" in f for f in report["failures"])


class TestArchitectureGateRunner:
    def test_run_architecture_gate_passes(self):
        from scripts.run_architecture_gate import PIPELINE_STEPS, run_architecture_gate

        reports = run_architecture_gate(snapshot_runs=20)
        for step in PIPELINE_STEPS:
            assert reports[step]["status"] == "PASS", reports[step].get("failures")

    def test_main_exit_code_zero(self):
        from scripts.run_architecture_gate import main

        assert main() == 0


class TestSnapshotCIGate:
    def test_validate_stored_ml_snapshot(self):
        snapshot = load_snapshot(_SNAPSHOTS / "ml_pipeline_v1_seed42.json")
        report = SnapshotCIGate().validate_snapshot(snapshot)
        assert report["status"] == "PASS", report["failures"]

    def test_compare_with_previous_passes_for_stored(self):
        gate = SnapshotCIGate()
        expected = load_snapshot(_SNAPSHOTS / "ml_pipeline_v1_seed42.json")
        actual = gate._run_ml_snapshot()
        report = gate.compare_with_previous(actual, expected)
        assert report["status"] == "PASS", report["failures"]

    def test_enforce_determinism_ml_20_runs(self):
        report = SnapshotCIGate().enforce_determinism(pipeline="ml", snapshot_runs=20)
        assert report["status"] == "PASS", report["failures"]

    def test_detects_schema_drift(self):
        expected = load_snapshot(_SNAPSHOTS / "ml_pipeline_v1_seed42.json")
        broken = dict(expected)
        broken["schema"] = {
            **expected["schema"],
            "top_keys": sorted(expected["schema"]["top_keys"]) + ["extra"],
        }
        report = SnapshotCIGate().compare_with_previous(broken, expected)
        assert report["status"] == "FAIL"
        assert any("schema drift" in f for f in report["failures"])

    def test_run_full_snapshot_check_passes(self):
        report = SnapshotCIGate().run_full_snapshot_check(snapshot_runs=20)
        assert report["status"] == "PASS", report["failures"]
