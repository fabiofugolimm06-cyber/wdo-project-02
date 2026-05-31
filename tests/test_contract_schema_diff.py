"""
Testes unitários do schema diff engine.
"""

from __future__ import annotations

from microstructure.contracts.contract_models import NestedOutputSchema, PipelineContract
from microstructure.contracts.schema_diff import diff_contracts
from microstructure.contracts.versions import ml_pipeline_contract_v1


def test_diff_reports_added_nested_required_as_non_breaking():
    v1 = ml_pipeline_contract_v1
    v2 = PipelineContract(
        contract_id="ml_pipeline_contract_v2",
        version="2.0.0",
        output_schema={**v1.output_schema, "metadata": "dict opcional"},
        required_top_keys=v1.required_top_keys | {"metadata"},
        forbidden_top_keys=v1.forbidden_top_keys,
        nested_schemas=v1.nested_schemas,
        allow_extra_top_keys=False,
    )
    diff = diff_contracts(v1, v2)
    assert "metadata" in diff.added_keys or any(
        "metadata" in m for m in diff.modified_constraints
    )
    assert diff.breaking_changes is False


def test_diff_forbidden_relaxation_is_breaking():
    v1 = ml_pipeline_contract_v1
    nested = v1.nested_schemas[0]
    relaxed = NestedOutputSchema(
        block_name=nested.block_name,
        required_keys=nested.required_keys,
        forbidden_keys=frozenset(),
        allow_extra_keys=False,
    )
    v2 = PipelineContract(
        contract_id=v1.contract_id,
        version="1.0.1",
        output_schema=dict(v1.output_schema),
        required_top_keys=v1.required_top_keys,
        forbidden_top_keys=v1.forbidden_top_keys,
        nested_schemas=(relaxed,),
        allow_extra_top_keys=False,
    )
    diff = diff_contracts(v1, v2)
    assert diff.breaking_changes is True
