"""
microstructure/features/datasets.py
------------------------------------
Constrói matriz de features X a partir de OHLCV + Feature Registry.

Comportamento resiliente:
  - X sempre usa o índice de df
  - falha em uma feature não interrompe as demais (log + skip)
  - nunca retorna X vazio se ao menos uma feature computou
  - colunas finais: float32, sem duplicatas
"""

from __future__ import annotations

import logging
from typing import Sequence

import pandas as pd
import numpy as np

from microstructure.features.registry import REGISTRY, ensure_features_registered

logger = logging.getLogger(__name__)


def _validate_df_index(df: pd.DataFrame) -> None:
    """
    Requisito do Feature Engine: índice temporal obrigatório.

    Raises
    ------
    TypeError : índice não é pandas.DatetimeIndex.
    ValueError : índice não é monotônico crescente.
    """
    if not isinstance(df.index, pd.DatetimeIndex):
        raise TypeError("Index must be DatetimeIndex")
    if not df.index.is_monotonic_increasing:
        raise ValueError(
            "build_dataset: índice deve ser monotônico crescente (use sort_index)."
        )


def _dedupe_feature_names(names: Sequence[str]) -> list[str]:
    """Remove nomes duplicados preservando ordem."""
    seen: set[str] = set()
    out: list[str] = []
    for name in names:
        if name in seen:
            logger.warning(
                "build_dataset: nome de feature duplicado ignorado: '%s'", name
            )
            continue
        seen.add(name)
        out.append(name)
    return out


def _finalize_X(X: pd.DataFrame) -> pd.DataFrame:
    """Garante float32 e remove colunas duplicadas."""
    if X.columns.duplicated().any():
        dupes = X.columns[X.columns.duplicated()].tolist()
        logger.warning("build_dataset: colunas duplicadas removidas: %s", dupes)
        X = X.loc[:, ~X.columns.duplicated()]

    for col in X.columns:
        X[col] = pd.to_numeric(X[col], errors="coerce").astype(np.float32)

    return X


def _build_feature_matrix(
    df: pd.DataFrame,
    feature_names: Sequence[str] | None = None,
) -> tuple[pd.DataFrame, list[str], list[tuple[str, str]]]:
    """
    Monta matriz X aplicando features do REGISTRY.

    Returns
    -------
    X, succeeded_names, failed (name, error_msg)
    """
    _validate_df_index(df)
    ensure_features_registered()
    features = _dedupe_feature_names(feature_names or REGISTRY.list())

    if len(features) == 0:
        raise RuntimeError(
            "build_dataset: nenhuma feature no REGISTRY. "
            "Execute autodiscover() ou verifique sys.path."
        )

    X = pd.DataFrame(index=df.index.copy())
    succeeded: list[str] = []
    failed: list[tuple[str, str]] = []

    for name in features:
        if name in X.columns:
            logger.warning(
                "build_dataset: coluna '%s' já existe — pulando.", name
            )
            continue

        try:
            feature_cls = REGISTRY.get(name)
            feature = feature_cls()
            series = feature.compute(df)
            if len(series) != len(df):
                raise ValueError(
                    f"length mismatch: got {len(series)}, expected {len(df)}"
                )
            if not series.index.equals(df.index):
                series = series.reindex(df.index)

            X[name] = pd.to_numeric(series, errors="coerce").astype(np.float32)
            succeeded.append(name)
            logger.debug("build_dataset: feature '%s' OK", name)

        except Exception as exc:
            msg = str(exc)
            failed.append((name, msg))
            logger.warning(
                "build_dataset: feature '%s' ignorada — %s: %s",
                name,
                type(exc).__name__,
                msg,
            )

    return X, succeeded, failed


def build_dataset(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aplica todas as features registradas e retorna matriz X.

    Features com erro são ignoradas (log warning); o pipeline continua.

    Raises
    ------
    TypeError : índice não é DatetimeIndex.
    ValueError : DataFrame vazio ou índice não monotônico.
    RuntimeError : REGISTRY vazio ou nenhuma feature computou com sucesso.
    """
    if df is None or len(df) == 0:
        raise ValueError("build_dataset: DataFrame vazio.")

    df = df.copy()
    _validate_df_index(df)

    X, succeeded, failed = _build_feature_matrix(df)

    if X.shape[1] == 0:
        raise RuntimeError(
            "build_dataset: nenhuma coluna gerada (X vazio). "
            f"Sucesso: {succeeded}. Falhas: {failed}"
        )

    if failed:
        logger.info(
            "build_dataset: %d/%d features OK; ignoradas: %s",
            len(succeeded),
            len(succeeded) + len(failed),
            [f[0] for f in failed],
        )

    return _finalize_X(X)


# --- API opcional (warmup / metadados) ----------------------------------------

class DatasetBuilderConfig:
    def __init__(self, feature_names=None, drop_warmup_rows=True):
        self.feature_names = feature_names
        self.drop_warmup_rows = drop_warmup_rows


class DatasetResult:
    def __init__(self, X, feature_names, n_warmup_dropped, failed_features=None):
        self.X = X
        self.feature_names = feature_names
        self.n_warmup_dropped = n_warmup_dropped
        self.failed_features = failed_features or []


def build_dataset_with_meta(
    df: pd.DataFrame,
    config: DatasetBuilderConfig | None = None,
) -> DatasetResult:
    """build_dataset + drop de warmup global + metadados."""
    config = config or DatasetBuilderConfig()
    X, succeeded, failed = _build_feature_matrix(df, config.feature_names)

    if X.shape[1] == 0:
        raise RuntimeError(
            "build_dataset_with_meta: X vazio. " f"Falhas: {failed}"
        )

    X = _finalize_X(X)

    n_warmup = _global_warmup_rows(X)
    n_dropped = 0
    if config.drop_warmup_rows and n_warmup > 0:
        X = X.iloc[n_warmup:]
        n_dropped = n_warmup

    return DatasetResult(
        X=X,
        feature_names=list(X.columns),
        n_warmup_dropped=n_dropped,
        failed_features=failed,
    )


def _global_warmup_rows(X: pd.DataFrame) -> int:
    max_warmup = 0
    for col in X.columns:
        first_valid = X[col].first_valid_index()
        if first_valid is None:
            continue
        max_warmup = max(max_warmup, X.index.get_loc(first_valid))
    return max_warmup
