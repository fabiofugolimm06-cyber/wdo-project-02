"""
microstructure/model/determinism.py — reexport do determinismo global (compat v1).
"""

from microstructure.determinism import (
    MODEL_V1_RANDOM_SEED,
    WDO_PROJECT_RANDOM_SEED,
    set_global_determinism,
    set_model_v1_determinism,
)

__all__ = [
    "WDO_PROJECT_RANDOM_SEED",
    "MODEL_V1_RANDOM_SEED",
    "set_global_determinism",
    "set_model_v1_determinism",
]
