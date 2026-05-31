"""
breaking_change_detector.py — detecção explícita de breaking changes.
"""

from __future__ import annotations

from typing import Any, Mapping

from microstructure.contracts.contract_models import PipelineContract
from microstructure.contracts.schema_diff import diff_contracts


def _report(breaking: bool, changes: list[str]) -> dict[str, Any]:
    return {
        "breaking": breaking,
        "changes": sorted(changes),
    }


def _is_pipeline_contract_schema(schema: Mapping[str, Any]) -> bool:
    return (
        "contract_id" in schema
        and "required_top_keys" in schema
        and "output_schema" in schema
    )


def detect_removed_fields(
    old: Mapping[str, Any],
    new: Mapping[str, Any],
) -> dict[str, Any]:
    """Detecta campos removidos entre schemas (pipeline ou JSON-schema)."""
    changes: list[str] = []

    if _is_pipeline_contract_schema(old) and _is_pipeline_contract_schema(new):
        old_keys = frozenset(old.get("required_top_keys", []))
        new_keys = frozenset(new.get("required_top_keys", []))
        removed_top = sorted(old_keys - new_keys)
        for key in removed_top:
            changes.append(f"removed_top_key:{key}")

        old_nested = {n["block_name"]: n for n in old.get("nested_schemas", [])}
        new_nested = {n["block_name"]: n for n in new.get("nested_schemas", [])}
        for block, nested in old_nested.items():
            if block not in new_nested:
                changes.append(f"removed_nested_block:{block}")
                continue
            rem = sorted(
                frozenset(nested.get("required_keys", []))
                - frozenset(new_nested[block].get("required_keys", []))
            )
            for key in rem:
                changes.append(f"removed_nested_key:{block}.{key}")

        old_out = frozenset(old.get("output_schema", {}).keys())
        new_out = frozenset(new.get("output_schema", {}).keys())
        for key in sorted(old_out - new_out):
            changes.append(f"removed_output_schema:{key}")

    old_required = frozenset(old.get("required", []))
    new_required = frozenset(new.get("required", []))
    for key in sorted(old_required - new_required):
        changes.append(f"removed_required:{key}")

    old_props = old.get("properties", {})
    new_props = new.get("properties", {})
    if isinstance(old_props, dict) and isinstance(new_props, dict):
        for key in sorted(set(old_props) - set(new_props)):
            changes.append(f"removed_property:{key}")

    return _report(bool(changes), changes)


def detect_type_changes(
    old: Mapping[str, Any],
    new: Mapping[str, Any],
) -> dict[str, Any]:
    """Detecta mudanças de tipo em JSON-schema ``properties``."""
    changes: list[str] = []
    old_props = old.get("properties", {})
    new_props = new.get("properties", {})
    if not isinstance(old_props, dict) or not isinstance(new_props, dict):
        return _report(False, changes)

    for key in sorted(set(old_props) & set(new_props)):
        old_type = old_props[key].get("type") if isinstance(old_props[key], dict) else None
        new_type = new_props[key].get("type") if isinstance(new_props[key], dict) else None
        if old_type and new_type and old_type != new_type:
            changes.append(f"type_change:{key}:{old_type}->{new_type}")

    return _report(bool(changes), changes)


def detect_contract_breaking_changes(
    old: Mapping[str, Any],
    new: Mapping[str, Any],
) -> dict[str, Any]:
    """
    Detecção agregada — pipeline contracts via ``diff_contracts``,
    schemas genéricos via remoções + type changes.
    """
    changes: list[str] = []
    breaking = False

    removed = detect_removed_fields(old, new)
    changes.extend(removed["changes"])
    breaking = breaking or removed["breaking"]

    type_changes = detect_type_changes(old, new)
    changes.extend(type_changes["changes"])
    breaking = breaking or type_changes["breaking"]

    if _is_pipeline_contract_schema(old) and _is_pipeline_contract_schema(new):
        try:
            c_old = PipelineContract.from_dict(old)
            c_new = PipelineContract.from_dict(new)
            diff = diff_contracts(c_old, c_new)
            changes.extend(diff.modified_constraints)
            breaking = breaking or diff.breaking_changes
        except Exception as exc:  # noqa: BLE001
            changes.append(f"pipeline_diff_error:{exc}")
            breaking = True

    old_forbidden = old.get("forbidden_top_keys", [])
    new_forbidden = new.get("forbidden_top_keys", [])
    if isinstance(old_forbidden, list) and isinstance(new_forbidden, list):
        relaxed = sorted(set(old_forbidden) - set(new_forbidden))
        if relaxed:
            changes.append(f"forbidden_top_keys_relaxed:{relaxed}")
            breaking = True

    if old.get("allow_extra_top_keys") and not new.get("allow_extra_top_keys"):
        changes.append("allow_extra_top_keys:True->False")
        breaking = True

    return _report(breaking, changes)


def detect_schema_breaking_changes(
    old: Mapping[str, Any],
    new: Mapping[str, Any],
) -> dict[str, Any]:
    """Alias público — delega a ``detect_contract_breaking_changes``."""
    return detect_contract_breaking_changes(old, new)
