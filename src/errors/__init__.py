"""Error Taxonomy System — classificação estrutural de falhas."""

from src.errors.error_classifier import ErrorClassifier
from src.errors.error_types import ClassifiedError, ErrorLayer, ErrorType
from src.errors.failure_registry import FailureRecord, FailureRegistry

__all__ = [
    "ClassifiedError",
    "ErrorClassifier",
    "ErrorLayer",
    "ErrorType",
    "FailureRecord",
    "FailureRegistry",
]
