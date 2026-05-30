"""
Testes do Grid Search v1.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from microstructure.features.datasets import build_dataset
from microstructure.labeling import create_horizon_labels, drop_invalid_label_rows
from microstructure.model import drop_nan_feature_rows
from microstructure.model_registry import (
    get_best_model,
    load_registry,
    register_model,
    reset_registry,
    save_registry,
)
from microstructure.optimization import run_grid_search


@pytest.fixture(autouse=True)
def _reset_registry():
    reset_registry()
    yield
    reset_registry()


def _dataset(n: int = 350, seed: int = 11) -> tuple[pd.DataFrame, pd.Series]:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-03-01", periods=n, freq="min")
    price = 100 + np.cumsum(rng.normal(0, 0.5, size=n))
    fechamento = price.astype(np.float32)
    df = pd.DataFrame(
        {
            "abertura": fechamento,
            "alta": fechamento + 1,
            "baixa": fechamento - 1,
            "fechamento": fechamento,
            "volume": rng.integers(100, 1000, n).astype(np.float32),
        },
        index=idx,
    )
    X = build_dataset(df)
    y = create_horizon_labels(df, horizon=5)
    X_ml, y_ml = drop_invalid_label_rows(X, y)
    return drop_nan_feature_rows(X_ml, y_ml)


class TestRunGridSearch:
    def test_multiple_combinations(self):
        X, y = _dataset()
        result = run_grid_search(
            X,
            y,
            param_grid={"C": [0.1, 1.0, 10.0]},
            scoring="f1",
        )
        assert len(result["all_results"]) == 3
        assert "C" in result["best_params"]
        assert result["best_score"] >= 0.0

    def test_best_score_matches_all_results(self):
        X, y = _dataset(400)
        result = run_grid_search(
            X,
            y,
            param_grid={
                "C": [0.01, 1.0],
                "train_size": [0.65, 0.75],
            },
            scoring="f1",
        )
        assert len(result["all_results"]) == 4
        max_from_all = max(r["score"] for r in result["all_results"])
        assert result["best_score"] == pytest.approx(max_from_all)

    def test_invalid_scoring_raises(self):
        X, y = _dataset(100)
        with pytest.raises(ValueError, match="scoring"):
            run_grid_search(X, y, {"C": [1.0]}, scoring="auc")

    def test_empty_grid_raises(self):
        X, y = _dataset(80)
        with pytest.raises(ValueError, match="param_grid"):
            run_grid_search(X, y, {})


class TestGridSearchIntegration:
    def test_model_and_registry(self, tmp_path: Path, capsys):
        X, y = _dataset(450)
        result = run_grid_search(
            X,
            y,
            param_grid={"C": [0.1, 1.0, 5.0]},
            scoring="f1",
        )

        register_model(
            model_name="grid_search_best",
            model_type="LogisticRegression",
            parameters=result["best_params"],
            metrics=result["best_metrics"],
        )
        save_registry(tmp_path)

        reset_registry()
        load_registry(tmp_path)
        best = get_best_model(metric="f1")
        assert best["parameters"]["C"] == result["best_params"]["C"]

        print(f"best_params: {result['best_params']}, best_f1: {result['best_score']:.4f}")
        print("GRID SEARCH V1 OK")

        captured = capsys.readouterr()
        assert "GRID SEARCH V1 OK" in captured.out
