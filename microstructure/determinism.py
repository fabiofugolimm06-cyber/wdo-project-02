"""
microstructure/determinism.py — reprodutibilidade global do WDO PROJECT 02.

Chamar ``set_global_determinism()`` no início de pipelines, scripts e testes.
"""

from __future__ import annotations

import os
import random

import numpy as np

# Seed canônico do projeto (numpy, random, sklearn via random_state nos estimators)
WDO_PROJECT_RANDOM_SEED = 42

# Alias legado (Model v1)
MODEL_V1_RANDOM_SEED = WDO_PROJECT_RANDOM_SEED


def set_global_determinism(seed: int = WDO_PROJECT_RANDOM_SEED) -> int:
    """
    Fixa estado global para execuções reprodutíveis.

    - ``numpy.random`` (API legada)
    - ``random`` (stdlib)
    - ``PYTHONHASHSEED`` (se ainda não definido no processo)
    - sklearn: use ``random_state={seed}`` nos estimators (trainer, grid_search)

    Dados sintéticos devem usar ``numpy.random.default_rng(seed)`` explícito.
    """
    seed = int(seed)

    os.environ.setdefault("PYTHONHASHSEED", str(seed))
    np.random.seed(seed)
    random.seed(seed)

    return seed


def set_model_v1_determinism(seed: int = WDO_PROJECT_RANDOM_SEED) -> int:
    """Alias para compatibilidade com ``microstructure.model``."""
    return set_global_determinism(seed)
