"""
protected_paths.py — áreas protegidas do sistema (alteração só via pipeline).
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Any

# Áreas lógicas → prefixos relativos ao root do projeto (POSIX normalizado).
PROTECTED_AREAS: dict[str, tuple[str, ...]] = {
    "contracts": (
        "microstructure/contracts",
        "src/contracts",
    ),
    "data": (
        "src/contracts/data",
    ),
    "evolution": (
        "src/evolution",
    ),
    "snapshot_spec": (
        "src/snapshot_spec",
        "tests/snapshots",
    ),
    "ci": (
        "src/ci",
        ".github/workflows",
        "scripts/run_architecture_gate.py",
    ),
}


class ProtectedPathError(ValueError):
    """Violação de path protegido."""


def _normalize_relative(path: str | Path) -> str:
    raw = str(path).replace("\\", "/").lstrip("/")
    return PurePosixPath(raw).as_posix()


def classify_path(path: str | Path) -> str | None:
    """Retorna área protegida ou None se path não protegido."""
    rel = _normalize_relative(path)
    for area, prefixes in PROTECTED_AREAS.items():
        for prefix in prefixes:
            norm_prefix = _normalize_relative(prefix)
            if rel == norm_prefix or rel.startswith(f"{norm_prefix}/"):
                return area
    return None


def is_protected_path(path: str | Path) -> bool:
    return classify_path(path) is not None


def validate_modification_path(
    path: str | Path,
    *,
    change_type: str,
    via_pipeline: bool = False,
) -> dict[str, Any]:
    """
    Valida modificação em path.

    ``change_type``: ``in_place`` | ``version_bump`` | ``registry_append``
    """
    failures: list[str] = []
    area = classify_path(path)
    rel = _normalize_relative(path)

    if area is None:
        return {"valid": True, "area": None, "failures": []}

    if change_type == "in_place" and not via_pipeline:
        failures.append(
            f"{rel}: alteração in-place em área protegida {area!r} "
            f"sem pipeline (version bump / registry obrigatório)."
        )

    if change_type not in {"in_place", "version_bump", "registry_append"}:
        failures.append(f"{rel}: change_type inválido {change_type!r}.")

    if area in PROTECTED_AREAS and change_type == "in_place":
        failures.append(
            f"{rel}: área {area!r} proíbe mutação in-place."
        )

    return {
        "valid": len(failures) == 0,
        "area": area,
        "failures": sorted(failures),
    }
