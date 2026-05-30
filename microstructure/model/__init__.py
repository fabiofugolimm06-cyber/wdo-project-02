"""
microstructure.model — Model Engine (Stage 06, baseline ML).
"""

from microstructure.determinism import WDO_PROJECT_RANDOM_SEED, set_global_determinism
from microstructure.model.determinism import MODEL_V1_RANDOM_SEED, set_model_v1_determinism
from microstructure.model.metrics import evaluate_classifier
from microstructure.model.predict import generate_ml_signal, predict_probabilities
from microstructure.model.split import train_test_split_time_series
from microstructure.model.pipeline import pipeline_fingerprint, run_ml_pipeline_v1
from microstructure.model.trainer import train_logistic_model
from microstructure.model.utils import drop_nan_feature_rows, report_nan_features
from microstructure.model.purged_kfold import (
    generate_purged_kfold_splits,
    purged_kfold_validation,
)
from microstructure.model.walkforward import walk_forward_validation

__all__ = [
    "WDO_PROJECT_RANDOM_SEED",
    "set_global_determinism",
    "MODEL_V1_RANDOM_SEED",
    "set_model_v1_determinism",
    "run_ml_pipeline_v1",
    "pipeline_fingerprint",
    "train_test_split_time_series",
    "train_logistic_model",
    "evaluate_classifier",
    "predict_probabilities",
    "generate_ml_signal",
    "drop_nan_feature_rows",
    "report_nan_features",
    "walk_forward_validation",
    "generate_purged_kfold_splits",
    "purged_kfold_validation",
]
