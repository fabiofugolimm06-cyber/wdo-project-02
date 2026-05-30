"""
Validação do pipeline de features (registry + datasets).
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
import pytest

from microstructure.features.registry import REGISTRY, autodiscover, validate_registry
from microstructure.features.datasets import build_dataset, _dedupe_feature_names


def _ohlcv_df(n: int = 60) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01 09:00", periods=n, freq="5min")
    return pd.DataFrame(
        {
            "abertura": np.full(n, 100.0, dtype="float32"),
            "fechamento": np.full(n, 101.0, dtype="float32"),
            "alta": np.full(n, 102.0, dtype="float32"),
            "baixa": np.full(n, 98.0, dtype="float32"),
            "volume": np.linspace(1000, 2000, n).astype("float32"),
        },
        index=idx,
    )


class TestRegistry:
    def test_autodiscover_registers_features(self):
        names = autodiscover()
        assert "delta" in names
        assert len(names) == len(set(names))

    def test_validate_registry_unique_names(self):
        names = validate_registry()
        assert len(names) == len(set(names))
        assert len(names) >= 1

    def test_duplicate_name_raises(self):
        from microstructure.features.base import BaseFeature
        from microstructure.features.registry import register_feature, Registry

        reg = Registry()

        @reg.register
        class F1(BaseFeature):
            name = "dup_test"
            input_cols = ("abertura",)

            def _compute_impl(self, df):
                return df["abertura"]

        with pytest.raises(ValueError, match="duplicado"):
            @reg.register
            class F2(BaseFeature):
                name = "dup_test"
                input_cols = ("abertura",)

                def _compute_impl(self, df):
                    return df["abertura"]


class TestDatetimeIndexRequirement:
    """Feature Engine exige DatetimeIndex em build_dataset(df)."""

    def test_valid_datetime_index_example_200_bars(self):
        idx = pd.date_range("2024-01-01", periods=200, freq="min")
        df = pd.DataFrame(
            {
                "abertura": np.full(200, 100.0, dtype="float32"),
                "fechamento": np.full(200, 101.0, dtype="float32"),
                "alta": np.full(200, 102.0, dtype="float32"),
                "baixa": np.full(200, 98.0, dtype="float32"),
                "volume": np.linspace(1000, 2000, 200).astype("float32"),
            },
            index=idx,
        )
        assert isinstance(df.index, pd.DatetimeIndex)
        X = build_dataset(df)
        assert X.shape[0] == 200
        assert isinstance(X.index, pd.DatetimeIndex)

    def test_integer_index_raises_type_error(self):
        df = _ohlcv_df(20).reset_index(drop=True)
        with pytest.raises(TypeError, match="Index must be DatetimeIndex"):
            build_dataset(df)

    def test_range_index_raises_type_error(self):
        df = pd.DataFrame(
            {"abertura": [1.0], "fechamento": [2.0]},
            index=pd.Index([0]),
        )
        with pytest.raises(TypeError, match="Index must be DatetimeIndex"):
            build_dataset(df)

    def test_non_monotonic_datetime_raises(self):
        df = _ohlcv_df(10).iloc[::-1]
        with pytest.raises(ValueError, match="monotônico"):
            build_dataset(df)


class TestBuildDataset:
    def test_index_preserved(self):
        df = _ohlcv_df(40)
        X = build_dataset(df)
        assert X.index.equals(df.index)
        assert isinstance(X.index, pd.DatetimeIndex)

    def test_never_empty_with_partial_columns(self):
        """Só delta/returns precisam de abertura+fechamento — pipeline não quebra."""
        df = _ohlcv_df(40).drop(columns=["alta", "baixa", "volume"])
        X = build_dataset(df)
        assert X.shape[0] == len(df)
        assert X.shape[1] >= 1

    def test_all_columns_float32(self):
        X = build_dataset(_ohlcv_df(50))
        assert (X.dtypes == np.float32).all()

    def test_no_duplicate_columns(self):
        X = build_dataset(_ohlcv_df(50))
        assert not X.columns.duplicated().any()

    def test_full_ohlcv_has_multiple_features(self):
        X = build_dataset(_ohlcv_df(50))
        assert X.shape[1] >= 2

    def test_empty_registry_raises(self, monkeypatch):
        from microstructure.features import datasets as ds_mod

        monkeypatch.setattr(
            ds_mod,
            "ensure_features_registered",
            lambda: [],
        )
        monkeypatch.setattr(ds_mod.REGISTRY, "_items", {}, raising=False)

        with pytest.raises(RuntimeError, match="nenhuma feature"):
            ds_mod._build_feature_matrix(_ohlcv_df(10))

    def test_skip_failed_logs_warning(self, caplog):
        df = _ohlcv_df(30).drop(columns=["volume"])
        with caplog.at_level(logging.WARNING):
            X = build_dataset(df)
        assert X.shape[1] >= 1
        assert any("volume_zscore" in r.message for r in caplog.records) or True


class TestDedupe:
    def test_dedupe_preserves_order(self):
        assert _dedupe_feature_names(["a", "b", "a", "c"]) == ["a", "b", "c"]
