"""
microstructure/livesim/engine.py — simulação live streaming bar a bar (v1).
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

import pandas as pd
from sklearn.linear_model import LogisticRegression

from microstructure.execution import simulate_execution
from microstructure.features.datasets import build_dataset
from microstructure.model.predict import generate_ml_signal, predict_probabilities
from microstructure.papertrading import PaperTradingEngine
from microstructure.strategy_config import validate_strategy_config


class LiveSimulationEngine:
    """
    Processamento incremental OHLCV → sinal ML → risk → paper trading.

    Causal: em cada barra usa apenas ``df.iloc[:bar_index + 1]`` para features.
    """

    def __init__(self) -> None:
        self._df: pd.DataFrame | None = None
        self._model: LogisticRegression | None = None
        self._config: dict[str, Any] | None = None
        self._paper: PaperTradingEngine | None = None
        self._bar_index: int = -1
        self._price_col: str = "fechamento"
        self._ml_threshold: float = 0.55
        self._min_bars: int = 5
        self._state: dict[str, Any] | None = None
        self._signal_history: list[int] = []
        self._last_raw_signal: int = 0
        self._last_filtered_signal: int = 0

    def _resolve_risk_params(
        self,
        risk_engine: dict[str, Any] | None,
    ) -> dict[str, float]:
        if risk_engine is None:
            return {}
        return {
            k: float(risk_engine[k])
            for k in ("daily_loss_limit", "max_drawdown_limit")
            if k in risk_engine
        }

    def run_stream(
        self,
        df: pd.DataFrame,
        model: LogisticRegression,
        strategy_config: dict[str, Any],
        risk_engine: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Executa simulação live sequencial sobre ``df``.

        Parameters
        ----------
        df : OHLCV com DatetimeIndex monotônico.
        model : modelo treinado (Model v1).
        strategy_config : Strategy Config v1.
        risk_engine : opcional ``daily_loss_limit``, ``max_drawdown_limit``.

        Returns
        -------
        Estado final com ``equity_curve``, ``events``, ``execution_summary``.
        """
        if df is None or len(df) == 0:
            raise ValueError("run_stream: DataFrame vazio.")
        if not isinstance(df.index, pd.DatetimeIndex):
            raise TypeError("run_stream: índice deve ser DatetimeIndex.")
        if not df.index.is_monotonic_increasing:
            raise ValueError("run_stream: índice deve ser monotônico crescente.")

        validate_strategy_config(strategy_config)

        self._df = df
        self._model = model
        self._config = strategy_config
        params = strategy_config["parameters"]
        self._price_col = str(params["data"].get("price_col", "fechamento"))
        self._ml_threshold = float(params["model"].get("ml_threshold", 0.55))
        self._min_bars = max(
            5,
            int(params["labeling"].get("horizon", 5)) + 2,
        )

        capital = float(params["execution"]["initial_capital"])
        risk_kwargs = self._resolve_risk_params(risk_engine)
        self._paper = PaperTradingEngine(
            initial_capital=capital,
            strategy_config=strategy_config,
            **risk_kwargs,
        )
        self._paper.initialize_state()

        self._bar_index = -1
        self._signal_history = []
        self._state = {
            "current_position": 0,
            "equity_curve": [],
            "events": [],
        }

        self.log_event("stream_start", {"bars": len(df)})

        for i in range(len(df)):
            self.step(i)

        self._attach_execution_summary()
        self.log_event("stream_end", {"bars_processed": len(df)})
        return self.get_state()

    def step(self, bar_index: int) -> dict[str, Any]:
        """Processa uma barra (apenas dados até ``bar_index`` inclusive)."""
        if self._df is None or self._paper is None:
            raise RuntimeError("LiveSimulationEngine: chame run_stream() ou configure df.")

        n = len(self._df)
        if bar_index < 0 or bar_index >= n:
            raise IndexError(f"step: bar_index={bar_index} fora de [0, {n}).")

        self._bar_index = bar_index
        bar = self._df.iloc[bar_index]
        price = float(bar[self._price_col])
        ts = self._df.index[bar_index]

        raw_signal = self.emit_signal()
        self._paper.update_position(price)
        self._paper.on_signal(raw_signal)
        paper_state = self._paper.get_state()

        self._last_raw_signal = raw_signal
        self._last_filtered_signal = int(paper_state["position"])
        self._signal_history.append(raw_signal)

        self.update_state(paper_state, timestamp=ts, price=price)
        self.log_event(
            "bar",
            {
                "bar_index": bar_index,
                "timestamp": str(ts),
                "price": price,
                "raw_signal": raw_signal,
                "position": paper_state["position"],
                "current_pnl": paper_state["current_pnl"],
            },
        )
        return self.get_state()

    def emit_signal(self) -> int:
        """
        Gera sinal ML usando apenas histórico até a barra atual (sem lookahead).
        """
        if self._df is None or self._model is None:
            raise RuntimeError("emit_signal: engine não configurado.")

        i = self._bar_index
        if i < 0:
            raise RuntimeError("emit_signal: bar_index não definido — chame step().")

        if i + 1 < self._min_bars:
            return 0

        hist = self._df.iloc[: i + 1]
        try:
            X = build_dataset(hist)
        except (ValueError, TypeError):
            return 0

        if len(X) == 0:
            return 0

        x_row = X.iloc[[-1]]
        if x_row.isna().any(axis=None):
            return 0

        try:
            proba = predict_probabilities(self._model, x_row)
            sig = int(generate_ml_signal(proba, threshold=self._ml_threshold)[0])
        except (ValueError, IndexError):
            return 0

        return sig

    def update_state(
        self,
        paper_state: dict[str, Any] | None = None,
        timestamp: pd.Timestamp | None = None,
        price: float | None = None,
    ) -> dict[str, Any]:
        """Atualiza estado agregado live + curva de equity."""
        state = self._require_state()
        ps = paper_state or self._paper.get_state() if self._paper else {}

        equity = float(ps.get("capital", 0)) + float(ps.get("current_pnl", 0))
        state["current_position"] = int(ps.get("position", 0))

        point = {
            "bar_index": self._bar_index,
            "timestamp": str(timestamp) if timestamp is not None else None,
            "price": price,
            "equity": equity,
            "current_pnl": float(ps.get("current_pnl", 0)),
            "position": state["current_position"],
        }
        state["equity_curve"].append(point)
        return self.get_state()

    def log_event(self, event_type: str, payload: dict[str, Any]) -> None:
        """Registra evento com timestamp da barra atual (se houver)."""
        state = self._require_state()
        ts = None
        if self._df is not None and 0 <= self._bar_index < len(self._df):
            ts = str(self._df.index[self._bar_index])

        state["events"].append({
            "type": event_type,
            "timestamp": ts,
            "bar_index": self._bar_index,
            "payload": deepcopy(payload),
        })

    def _attach_execution_summary(self) -> None:
        """Resumo Execution v1 sobre série de sinais gerada (pós-stream)."""
        if self._df is None or not self._signal_history:
            return

        idx = self._df.index[: len(self._signal_history)]
        signals = pd.Series(self._signal_history, index=idx, name="signal")
        capital = float(
            self._config["parameters"]["execution"]["initial_capital"]  # type: ignore
        )
        pos_size = float(
            self._config["parameters"]["execution"]["position_size"]  # type: ignore
        )

        try:
            _, metrics = simulate_execution(
                signals,
                initial_capital=capital,
                position_size=pos_size,
            )
            self.log_event("execution_summary", metrics)
        except ValueError:
            self.log_event("execution_summary", {"error": "simulate_execution_failed"})

    def _require_state(self) -> dict[str, Any]:
        if self._state is None:
            raise RuntimeError(
                "LiveSimulationEngine: estado não inicializado."
            )
        return self._state

    def get_state(self) -> dict[str, Any]:
        return deepcopy(self._state) if self._state else {}
