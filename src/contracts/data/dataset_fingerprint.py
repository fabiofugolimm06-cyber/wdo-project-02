"""
dataset_fingerprint.py — fingerprint determinístico SHA256 para OHLCV.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

import numpy as np
import pandas as pd

OHLCV_COLUMNS: tuple[str, ...] = (
    "abertura",
    "alta",
    "baixa",
    "fechamento",
    "volume",
)


class FingerprintError(ValueError):
    """Erro na geração ou validação de fingerprint."""


def _canonical_json(obj: Mapping[str, Any] | list[Any]) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _fmt_float(value: Any) -> str:
    return format(float(value), ".12g")


def _require_ohlcv_frame(data: pd.DataFrame) -> None:
    if not isinstance(data, pd.DataFrame):
        raise FingerprintError("generate_fingerprint: data deve ser pd.DataFrame.")
    if data.empty:
        raise FingerprintError("generate_fingerprint: DataFrame vazio.")
    missing = [c for c in OHLCV_COLUMNS if c not in data.columns]
    if missing:
        raise FingerprintError(
            f"generate_fingerprint: colunas OHLCV ausentes: {missing}."
        )
    if not isinstance(data.index, pd.DatetimeIndex):
        raise FingerprintError(
            "generate_fingerprint: index deve ser DatetimeIndex monotônico."
        )
    if not data.index.is_monotonic_increasing:
        raise FingerprintError(
            "generate_fingerprint: timestamps devem ser monotônicos crescentes."
        )
    if data.index.has_duplicates:
        raise FingerprintError(
            "generate_fingerprint: timestamps duplicados não permitidos."
        )


def _canonical_ohlcv_payload(data: pd.DataFrame) -> str:
    """Serialização canônica: ordem temporal + valores OHLCV."""
    _require_ohlcv_frame(data)
    lines: list[str] = []
    for ts, row in data.iterrows():
        parts = [_fmt_float(row[c]) for c in OHLCV_COLUMNS]
        lines.append(f"{pd.Timestamp(ts).isoformat()}|" + "|".join(parts))
    return "\n".join(lines)


def _sha256_hex(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def generate_schema_hash(schema: Mapping[str, Any]) -> str:
    """Hash determinístico de schema JSON-schema compatible."""
    if not isinstance(schema, Mapping):
        raise FingerprintError("generate_schema_hash: schema deve ser dict.")
    if not schema:
        raise FingerprintError("generate_schema_hash: schema vazio.")
    return _sha256_hex(_canonical_json(dict(schema)))


def generate_dataset_hash(data: pd.DataFrame) -> str:
    """
    Hash determinístico do conteúdo OHLCV + ordem temporal.

    Independente de schema e normalização.
    """
    return _sha256_hex(_canonical_ohlcv_payload(data))


def generate_fingerprint(
    data: pd.DataFrame,
    schema: Mapping[str, Any],
    *,
    normalization_version: str = "none:v1",
) -> str:
    """
    Fingerprint SHA256 canônico.

    Combina ``dataset_hash``, ``schema_hash`` e ``normalization_version``.
    Mesmo input → mesmo output sempre.
    """
    if not normalization_version or not str(normalization_version).strip():
        raise FingerprintError(
            "generate_fingerprint: normalization_version obrigatório."
        )
    schema_hash = generate_schema_hash(schema)
    dataset_hash = generate_dataset_hash(data)
    canonical = "|".join(
        (
            f"dataset_hash={dataset_hash}",
            f"schema_hash={schema_hash}",
            f"normalization_version={normalization_version}",
        )
    )
    return _sha256_hex(canonical)


def verify_fingerprint(
    data: pd.DataFrame,
    schema: Mapping[str, Any],
    fingerprint: str,
    *,
    normalization_version: str = "none:v1",
) -> bool:
    """Compara fingerprint esperado com o recalculado."""
    expected = generate_fingerprint(
        data,
        schema,
        normalization_version=normalization_version,
    )
    return expected == fingerprint
