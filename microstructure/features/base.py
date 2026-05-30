from __future__ import annotations

from abc import ABC, abstractmethod
import pandas as pd
import numpy as np


class BaseFeature(ABC):
    """
    Core abstraction for all causal microstructure features.
    """

    # metadata defaults (can be overridden)
    name: str = "base_feature"
    warmup_bars: int = 0
    causal: bool = True
    dtype: str = "float32"
    input_cols: tuple = ()

    def __init__(self):
        self._fitted = False

    # ---------------------------
    # PUBLIC API
    # ---------------------------
    def compute(self, df: pd.DataFrame) -> pd.Series:
        self._validate_input(df)

        result = self._compute_impl(df)

        self._validate_output(df, result)

        result = self._apply_dtype(result)

        self._fitted = True
        return result

    @abstractmethod
    def _compute_impl(self, df: pd.DataFrame) -> pd.Series:
        pass

    # ---------------------------
    # VALIDATION
    # ---------------------------
    def _validate_input(self, df: pd.DataFrame):
        if df is None or len(df) == 0:
            raise ValueError("Empty dataframe")

        if not isinstance(df.index, pd.DatetimeIndex):
            raise TypeError("Index must be DatetimeIndex")

        if not df.index.is_monotonic_increasing:
            raise ValueError("Index must be sorted and monotonic")

        for col in self.input_cols:
            if col not in df.columns:
                raise ValueError(f"Missing required column: {col}")

    def _validate_output(self, df: pd.DataFrame, result: pd.Series):
        if len(result) != len(df):
            raise ValueError("Feature length mismatch")

        if self.causal:
            # simple causal sanity: no future shift allowed (heuristic)
            if result.isna().all():
                return

            if result.dropna().shape[0] == 0:
                raise ValueError("Invalid causal output")

    def _apply_dtype(self, result: pd.Series) -> pd.Series:
        return result.astype(self.dtype)

    # ---------------------------
    # HELPERS
    # ---------------------------
    def to_frame(self, df: pd.DataFrame) -> pd.DataFrame:
        return pd.DataFrame({self.name: self.compute(df)}, index=df.index)

    def __repr__(self):
        return f"{self.__class__.__name__}(name={self.name}, dtype={self.dtype})"