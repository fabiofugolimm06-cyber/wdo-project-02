"""
tests/test_data_contract_v1.py — Data Contract Layer v1 (fingerprint + registry).
"""

from __future__ import annotations

import pandas as pd
import pytest

from src.contracts.data import (
    DataContract,
    DataContractIntegrityError,
    DatasetDuplicateError,
    DatasetNotFoundError,
    DatasetRegistry,
    OHLCV_SCHEMA_V1,
    generate_dataset_hash,
    generate_fingerprint,
    generate_schema_hash,
)
from tests.ohlcv_data import make_ohlcv


@pytest.fixture
def ohlcv_200() -> pd.DataFrame:
    return make_ohlcv(n=200, seed=42)


@pytest.fixture
def registry() -> DatasetRegistry:
    return DatasetRegistry()


def test_schema_hash_deterministic() -> None:
    h1 = generate_schema_hash(OHLCV_SCHEMA_V1)
    h2 = generate_schema_hash(OHLCV_SCHEMA_V1)
    assert h1 == h2
    assert len(h1) == 64


def test_fingerprint_deterministic_20_runs(ohlcv_200: pd.DataFrame) -> None:
    fps = {
        generate_fingerprint(ohlcv_200, OHLCV_SCHEMA_V1, normalization_version="none:v1")
        for _ in range(20)
    }
    assert len(fps) == 1


def test_fingerprint_changes_with_data_or_normalization(
    ohlcv_200: pd.DataFrame,
) -> None:
    fp_base = generate_fingerprint(
        ohlcv_200, OHLCV_SCHEMA_V1, normalization_version="none:v1"
    )
    other = make_ohlcv(n=200, seed=43)
    fp_other_seed = generate_fingerprint(
        other, OHLCV_SCHEMA_V1, normalization_version="none:v1"
    )
    fp_other_norm = generate_fingerprint(
        ohlcv_200, OHLCV_SCHEMA_V1, normalization_version="zscore:v1"
    )
    assert fp_base != fp_other_seed
    assert fp_base != fp_other_norm


def test_dataset_hash_independent_of_schema(ohlcv_200: pd.DataFrame) -> None:
    h1 = generate_dataset_hash(ohlcv_200)
    alt_schema = dict(OHLCV_SCHEMA_V1)
    alt_schema["title"] = "alt"
    h2 = generate_dataset_hash(ohlcv_200)
    assert h1 == h2
    assert h1 != generate_fingerprint(ohlcv_200, alt_schema)


def test_data_contract_from_dataframe(ohlcv_200: pd.DataFrame) -> None:
    contract = DataContract.from_dataframe(
        ohlcv_200,
        dataset_id="wdo_synthetic",
        symbol="WDO",
        timeframe="1min",
        source="tests.make_ohlcv",
        version="v1",
    )
    assert contract.dataset_id == "wdo_synthetic"
    assert contract.version == "v1"
    assert len(contract.fingerprint) == 64
    assert contract.schema_hash == generate_schema_hash(OHLCV_SCHEMA_V1)
    contract.verify_against_data(ohlcv_200)


def test_data_contract_rejects_bad_schema_hash(ohlcv_200: pd.DataFrame) -> None:
    base = DataContract.from_dataframe(
        ohlcv_200,
        dataset_id="wdo_synthetic",
        symbol="WDO",
        timeframe="1min",
        source="tests.make_ohlcv",
        version="v1",
    )
    with pytest.raises(DataContractIntegrityError):
        DataContract(
            dataset_id=base.dataset_id,
            symbol=base.symbol,
            timeframe=base.timeframe,
            source=base.source,
            schema=base.schema,
            schema_hash="0" * 64,
            dataset_hash=base.dataset_hash,
            fingerprint=base.fingerprint,
            version=base.version,
            normalization_version=base.normalization_version,
            missing_data_policy=base.missing_data_policy,
            lineage_enabled=base.lineage_enabled,
        )


def test_registry_register_get_list(
    registry: DatasetRegistry,
    ohlcv_200: pd.DataFrame,
) -> None:
    c1 = DataContract.from_dataframe(
        ohlcv_200,
        dataset_id="wdo_synthetic",
        symbol="WDO",
        timeframe="1min",
        source="tests.make_ohlcv",
        version="v1",
    )
    registry.register(c1)
    assert registry.get("wdo_synthetic", "v1") == c1
    assert registry.get("wdo_synthetic") == c1
    assert len(registry.list()) == 1
    assert len(registry.list(symbol="WDO")) == 1
    assert registry.list(symbol="OTHER") == []


def test_registry_rejects_duplicate_fingerprint(
    registry: DatasetRegistry,
    ohlcv_200: pd.DataFrame,
) -> None:
    c1 = DataContract.from_dataframe(
        ohlcv_200,
        dataset_id="wdo_a",
        symbol="WDO",
        timeframe="1min",
        source="tests.make_ohlcv",
        version="v1",
    )
    c2 = DataContract.from_dataframe(
        ohlcv_200,
        dataset_id="wdo_b",
        symbol="WDO",
        timeframe="1min",
        source="tests.make_ohlcv",
        version="v1",
    )
    registry.register(c1)
    with pytest.raises(DatasetDuplicateError):
        registry.register(c2)


def test_registry_requires_new_version_for_same_id(
    registry: DatasetRegistry,
    ohlcv_200: pd.DataFrame,
) -> None:
    c_v1 = DataContract.from_dataframe(
        ohlcv_200,
        dataset_id="wdo_synthetic",
        symbol="WDO",
        timeframe="1min",
        source="tests.make_ohlcv",
        version="v1",
    )
    registry.register(c_v1)
    with pytest.raises(DatasetDuplicateError):
        registry.register(c_v1)

    other = make_ohlcv(n=200, seed=99)
    c_v2 = DataContract.from_dataframe(
        other,
        dataset_id="wdo_synthetic",
        symbol="WDO",
        timeframe="1min",
        source="tests.make_ohlcv",
        version="v2",
    )
    registry.register(c_v2)
    assert registry.get("wdo_synthetic", "v1") == c_v1
    assert registry.get("wdo_synthetic", "v2") == c_v2
    assert registry.get("wdo_synthetic") == c_v2


def test_registry_validate_integrity(
    registry: DatasetRegistry,
    ohlcv_200: pd.DataFrame,
) -> None:
    registry.register(
        DataContract.from_dataframe(
            ohlcv_200,
            dataset_id="wdo_synthetic",
            symbol="WDO",
            timeframe="1min",
            source="tests.make_ohlcv",
            version="v1",
        )
    )
    report = registry.validate_integrity()
    assert report["valid"] is True
    assert report["dataset_count"] == 1
    assert report["errors"] == []


def test_registry_not_found(registry: DatasetRegistry) -> None:
    with pytest.raises(DatasetNotFoundError):
        registry.get("missing")


def test_verify_against_data_fails_on_tamper(
    ohlcv_200: pd.DataFrame,
) -> None:
    contract = DataContract.from_dataframe(
        ohlcv_200,
        dataset_id="wdo_synthetic",
        symbol="WDO",
        timeframe="1min",
        source="tests.make_ohlcv",
        version="v1",
    )
    tampered = ohlcv_200.copy()
    tampered.iloc[0, tampered.columns.get_loc("fechamento")] = 999.0
    with pytest.raises(DataContractIntegrityError):
        contract.verify_against_data(tampered)


def test_fingerprint_rejects_non_monotonic_index() -> None:
    df = make_ohlcv(n=10)
    shuffled = df.iloc[[3, 1, 2, 0, 4, 5, 6, 7, 8, 9]]
    with pytest.raises(ValueError):
        generate_fingerprint(shuffled, OHLCV_SCHEMA_V1)
