"""
microstructure/determinism.py — reprodutibilidade global do WDO PROJECT 02.
"""

from __future__ import annotations

import os
import random

import numpy as np

WDO_PROJECT_RANDOM_SEED = 42
MODEL_V1_RANDOM_SEED = WDO_PROJECT_RANDOM_SEED

# BLAS/OpenMP: paralelismo causa divergência numérica intermitente em CI
_THREAD_ENV_KEYS = (
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
    "BLIS_NUM_THREADS",
)


def apply_thread_limits() -> None:
    """Força operações lineares single-thread (determinismo sklearn/numpy)."""
    for key in _THREAD_ENV_KEYS:
        os.environ[key] = "1"


def set_global_determinism(seed: int = WDO_PROJECT_RANDOM_SEED) -> int:
    """
    Estado global reprodutível antes de cada pipeline / teste.

    - threads BLAS = 1
    - ``numpy`` + ``random`` (API legada)
    - ``PYTHONHASHSEED``
    - sklearn: usar ``random_state=seed`` nos estimators
    """
    apply_thread_limits()
    seed = int(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)
    np.random.seed(seed)
    random.seed(seed)
    return seed


def set_model_v1_determinism(seed: int = WDO_PROJECT_RANDOM_SEED) -> int:
    """Alias legado."""
    return set_global_determinism(seed)


# Aplicar limites de thread na importação (antes de numpy/sklearn em CI)
apply_thread_limits()
