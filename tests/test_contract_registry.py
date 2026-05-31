"""
Contract Registry — fonte única de verdade para contratos versionados.
"""

from __future__ import annotations

import pytest

from microstructure.contracts.contract_models import PipelineContract
from microstructure.contracts.registry import (
    CONTRACTS,
    ContractDuplicateError,
    ContractNotFoundError,
    ContractRegistry,
    ContractRegistryFrozenError,
    contract_registry,
    full_pipeline_contract_v1,
    get_contract,
    ml_pipeline_contract_v1,
)
from microstructure.contracts.versions import (
    full_pipeline_contract_v1 as _full_from_versions,
    ml_pipeline_contract_v1 as _ml_from_versions,
)


class TestGlobalRegistry:
    def test_contracts_map_matches_registered_keys(self):
        assert set(CONTRACTS.keys()) == set(contract_registry.list_contracts())

    def test_get_contract_by_registry_key(self):
        c = get_contract("ml_pipeline:v1")
        assert c.contract_id == "ml_pipeline_contract_v1"
        assert c.version == "1.0.0"

    def test_get_contract_by_contract_id(self):
        c = get_contract("full_pipeline_contract_v1")
        assert c.contract_id == "full_pipeline_contract_v1"

    def test_get_contract_by_active_type(self):
        c = get_contract("ml_pipeline")
        assert c is ml_pipeline_contract_v1

    def test_list_contracts_returns_all(self):
        listed = contract_registry.list_contracts()
        assert listed == ("full_pipeline:v1", "ml_pipeline:v1")

    def test_get_active_version(self):
        assert contract_registry.get_active_version("ml_pipeline") == "v1"
        assert contract_registry.get_active_version("full_pipeline") == "v1"

    def test_get_active_contract(self):
        active = contract_registry.get_active_contract("full_pipeline")
        assert active is full_pipeline_contract_v1

    def test_validate_contract_exists_true_for_known(self):
        assert contract_registry.validate_contract_exists("ml_pipeline:v1") is True

    def test_unknown_contract_raises(self):
        with pytest.raises(ContractNotFoundError):
            get_contract("does_not_exist:v99")

    def test_reexports_match_versions_module(self):
        assert ml_pipeline_contract_v1 is _ml_from_versions
        assert full_pipeline_contract_v1 is _full_from_versions

    def test_global_registry_is_frozen(self):
        assert contract_registry.is_frozen is True


class TestRegistryRegistrationRules:
    def test_duplicate_registry_key_rejected(self):
        reg = ContractRegistry()
        reg.register("ml_pipeline:v1", ml_pipeline_contract_v1)
        with pytest.raises(ContractDuplicateError, match="duplicada"):
            reg.register("ml_pipeline:v1", ml_pipeline_contract_v1)

    def test_duplicate_contract_id_rejected(self):
        reg = ContractRegistry()
        reg.register("ml_pipeline:v1", ml_pipeline_contract_v1)
        clone = PipelineContract(
            contract_id=ml_pipeline_contract_v1.contract_id,
            version="9.9.9",
            output_schema=dict(ml_pipeline_contract_v1.output_schema),
            required_top_keys=ml_pipeline_contract_v1.required_top_keys,
            forbidden_top_keys=ml_pipeline_contract_v1.forbidden_top_keys,
            nested_schemas=ml_pipeline_contract_v1.nested_schemas,
            allow_extra_top_keys=ml_pipeline_contract_v1.allow_extra_top_keys,
        )
        with pytest.raises(ContractDuplicateError, match="contract_id"):
            reg.register("ml_pipeline:v9", clone)

    def test_register_after_freeze_rejected(self):
        reg = ContractRegistry()
        reg.register("ml_pipeline:v1", ml_pipeline_contract_v1)
        reg.freeze()
        with pytest.raises(ContractRegistryFrozenError):
            reg.register("full_pipeline:v1", full_pipeline_contract_v1)

    def test_unknown_contract_type_for_active_version(self):
        reg = ContractRegistry()
        with pytest.raises(ContractNotFoundError):
            reg.get_active_version("backtest_only")
