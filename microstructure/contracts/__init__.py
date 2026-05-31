"""
microstructure/contracts — Contract-Based Pipeline System (registry central).

API pública preferencial
------------------------
- ``ContractRegistry`` / ``contract_registry``
- ``get_contract(contract_id)``
- ``ml_pipeline_contract_v1`` / ``full_pipeline_contract_v1``

Demais símbolos: re-exportados para compatibilidade; novos códigos devem usar
``get_contract()`` e submódulos explícitos (``enforcement``, ``schema_diff``, …).
"""

from microstructure.contracts.compatibility import (
    assert_ml_pipeline_regression_stable,
    get_backtest_metrics_block,
    get_model_metrics_block,
    resolve_regression_metric,
    validate_compatibility,
)
from microstructure.contracts.enforcement import (
    ContractViolationError,
    validate_full_pipeline_contract,
    validate_ml_contract,
)
from microstructure.contracts.contract_models import NestedOutputSchema, PipelineContract
from microstructure.contracts.pipeline_schemas import (
    E2E_BACKTEST_METRIC_REQUIRED_KEYS,
    E2E_EXECUTION_METRIC_REQUIRED_KEYS,
    E2E_PIPELINE_TOP_KEYS,
    FORBIDDEN_KEYS_IN_ML_METRICS,
    ML_METRIC_KEYS,
    ML_PIPELINE_RESULT_TOP_KEYS,
    validate_e2e_pipeline_result,
    validate_ml_metrics,
    validate_ml_pipeline_result,
)
from microstructure.contracts.registry import (
    CONTRACTS,
    ContractDuplicateError,
    ContractNotFoundError,
    ContractRegistry,
    ContractRegistryError,
    ContractRegistryFrozenError,
    contract_registry,
    full_pipeline_contract_v1,
    get_contract,
    ml_pipeline_contract_v1,
)
from microstructure.contracts.schema_diff import ContractDiffResult, diff_contracts
from microstructure.contracts.snapshot import (
    DEFAULT_NUMERIC_EPSILON,
    build_full_pipeline_snapshot,
    build_ml_pipeline_snapshot,
    compare_ml_snapshots,
    compare_pipeline_snapshots,
    load_snapshot,
    save_snapshot,
)

__all__ = [
    # Registry (fonte única de verdade)
    "ContractRegistry",
    "contract_registry",
    "get_contract",
    "CONTRACTS",
    "ml_pipeline_contract_v1",
    "full_pipeline_contract_v1",
    "ContractNotFoundError",
    "ContractDuplicateError",
    "ContractRegistryError",
    "ContractRegistryFrozenError",
    # Compatibilidade
    "PipelineContract",
    "NestedOutputSchema",
    "ContractDiffResult",
    "ML_METRIC_KEYS",
    "ML_PIPELINE_RESULT_TOP_KEYS",
    "E2E_PIPELINE_TOP_KEYS",
    "FORBIDDEN_KEYS_IN_ML_METRICS",
    "E2E_BACKTEST_METRIC_REQUIRED_KEYS",
    "E2E_EXECUTION_METRIC_REQUIRED_KEYS",
    "validate_ml_metrics",
    "validate_ml_pipeline_result",
    "validate_e2e_pipeline_result",
    "validate_compatibility",
    "get_model_metrics_block",
    "get_backtest_metrics_block",
    "resolve_regression_metric",
    "assert_ml_pipeline_regression_stable",
    "validate_ml_contract",
    "validate_full_pipeline_contract",
    "ContractViolationError",
    "diff_contracts",
    "build_ml_pipeline_snapshot",
    "build_full_pipeline_snapshot",
    "compare_ml_snapshots",
    "compare_pipeline_snapshots",
    "load_snapshot",
    "save_snapshot",
    "DEFAULT_NUMERIC_EPSILON",
]
