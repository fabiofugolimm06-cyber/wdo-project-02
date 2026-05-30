"""
microstructure/live/live_orchestrator_v1.py — orquestrador bar-by-bar (v1).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pandas as pd

from microstructure.core.decision_engine import run_decision_pipeline

_VALID_SIGNALS = {-1, 0, 1}


class RiskFilterAdapter:
    """Adaptador mínimo para ``risk_filter`` com interface ``.filter(signal)``."""

    def __init__(self, allow_trading: bool = True) -> None:
        self._allow_trading = allow_trading

    def filter(self, signal: int, allow_trading: bool | None = None) -> int:
        from microstructure.risk.risk_engine import risk_filter

        allow = self._allow_trading if allow_trading is None else allow_trading
        out = risk_filter([int(signal)], allow_trading=allow)
        return int(out["signals"][0])


class LiveOrchestratorV1:
    """
    Simula mercado em tempo real: decisão → risco → execution bridge, barra a barra.

    Causal: em cada ``t`` usa apenas ``df.iloc[: t + 1]`` (sem ``t+1`` em diante).
    """

    def __init__(
        self,
        decision_engine: Callable[..., dict[str, Any]] | None = None,
        risk_engine: Any | None = None,
        execution_bridge: Any | None = None,
        price_col: str = "fechamento",
    ) -> None:
        self._decision_fn = decision_engine or run_decision_pipeline
        self._risk_engine = risk_engine
        self._execution_bridge = execution_bridge
        self._price_col = price_col
        self._log: list[dict[str, Any]] = []

    def reset(self) -> None:
        self._log = []
        if self._execution_bridge is not None and hasattr(self._execution_bridge, "reset"):
            self._execution_bridge.reset()

    def run(
        self,
        df: pd.DataFrame,
        mode: str = "signal_only",
        **decision_kwargs: Any,
    ) -> dict[str, Any]:
        """
        Executa orquestração completa sobre ``df`` (ordem temporal).

        Parameters
        ----------
        df : OHLCV com DatetimeIndex monotônico.
        mode : modo repassado ao decision engine.
        **decision_kwargs : extras para ``run_decision_pipeline`` (ex.: ``model``).
        """
        self._validate_df(df)
        self.reset()

        if self._price_col not in df.columns:
            raise ValueError(
                f"LiveOrchestratorV1: coluna '{self._price_col}' ausente em df."
            )

        n = len(df)
        for t in range(n):
            slice_df = df.iloc[: t + 1].copy()
            ts = df.index[t]
            price = float(df[self._price_col].iloc[t])

            decision = self._decision_fn(slice_df, mode=mode, **decision_kwargs)
            signals = decision["signals"]
            if len(signals) == 0:
                raise RuntimeError(f"LiveOrchestratorV1: sinais vazios em t={t}.")

            signal = int(signals.iloc[-1])
            if signal not in _VALID_SIGNALS:
                raise ValueError(f"LiveOrchestratorV1: sinal inválido {signal} em t={t}.")

            if self._risk_engine is not None:
                if not hasattr(self._risk_engine, "filter"):
                    raise TypeError(
                        "risk_engine deve expor método filter(signal) -> int."
                    )
                signal = int(self._risk_engine.filter(signal))

            if self._execution_bridge is not None:
                if not hasattr(self._execution_bridge, "process_signal"):
                    raise TypeError(
                        "execution_bridge deve expor process_signal(signal, price, timestamp)."
                    )
                self._execution_bridge.process_signal(signal, price, ts)

            self._log.append({
                "timestamp": ts,
                "signal": signal,
                "price": price,
                "mode": mode,
                "bar_index": t,
            })

        return {
            "log": pd.DataFrame(self._log),
            "final_state": self._final_state(),
        }

    def _final_state(self) -> dict[str, int]:
        if not self._log:
            return {
                "total_signals": 0,
                "longs": 0,
                "shorts": 0,
                "flat": 0,
            }
        log_df = pd.DataFrame(self._log)
        sig = log_df["signal"].astype(int)
        return {
            "total_signals": int(len(sig)),
            "longs": int((sig == 1).sum()),
            "shorts": int((sig == -1).sum()),
            "flat": int((sig == 0).sum()),
        }

    @staticmethod
    def _validate_df(df: pd.DataFrame) -> None:
        if df is None or len(df) == 0:
            raise ValueError("LiveOrchestratorV1: DataFrame vazio.")
        if not isinstance(df.index, pd.DatetimeIndex):
            raise TypeError("LiveOrchestratorV1: índice deve ser DatetimeIndex.")
        if not df.index.is_monotonic_increasing:
            raise ValueError("LiveOrchestratorV1: índice deve ser monotônico crescente.")
