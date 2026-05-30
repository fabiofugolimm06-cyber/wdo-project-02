"""
microstructure/risk/guardian_integration_v1.py — integração RiskGuardian (v1).

Filtros por composição — não altera decision_engine, execution_bridge,
live_orchestrator nem papertrading.
"""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from typing import Any

import pandas as pd

from microstructure.risk.risk_guardian_v1 import RiskGuardianV1

_VALID_SIGNALS = frozenset({-1, 0, 1})


def state_from_paper(paper_state: dict[str, Any]) -> dict[str, Any]:
    """Monta estado do guardian a partir de ``PaperTradingEngine.get_state()``."""
    return {
        "daily_pnl": float(
            paper_state.get("current_pnl", paper_state.get("realized_pnl", 0.0))
        ),
        "current_drawdown": float(paper_state.get("current_drawdown", 0.0)),
        "exposure": abs(float(paper_state.get("position", 0)))
            * float(paper_state.get("position_units", 1.0)),
        "position": int(paper_state.get("position", 0)),
        "consecutive_losses": int(paper_state.get("consecutive_losses", 0)),
    }


def state_from_bridge_snapshot(risk_snapshot: dict[str, Any]) -> dict[str, Any]:
    """Estado a partir de ``ExecutionBridge.get_state()['risk_snapshot']``."""
    return {
        "daily_pnl": float(risk_snapshot.get("current_pnl", 0.0)),
        "current_drawdown": float(risk_snapshot.get("current_drawdown", 0.0)),
        "exposure": abs(float(risk_snapshot.get("position", 0))),
        "position": int(risk_snapshot.get("position", 0)),
    }


class RiskGuardianFilterAdapter:
    """Interface ``filter(signal)`` para ``LiveOrchestratorV1``."""

    def __init__(
        self,
        guardian: RiskGuardianV1,
        state_provider: Callable[[], dict[str, Any]] | None = None,
        position_size: float = 1.0,
    ) -> None:
        self._guardian = guardian
        self._state_provider = state_provider or guardian.get_state
        self._position_size = float(position_size)
        self._last_reason: str = ""

    @property
    def last_reason(self) -> str:
        return self._last_reason

    def filter(self, signal: int) -> int:
        state = self._state_provider()
        out = self._guardian.evaluate(
            state,
            {
                "signal": int(signal),
                "risk": {"position_size": self._position_size},
            },
        )
        self._last_reason = out["reason"]
        return int(out["approved_signal"])


class GuardedExecutionBridge:
    """
    Envolve ``ExecutionBridge`` — nenhum ``process_signal`` sem passar pelo guardian.
    """

    def __init__(
        self,
        bridge: Any,
        guardian: RiskGuardianV1,
        state_provider: Callable[[], dict[str, Any]] | None = None,
        position_size: float = 1.0,
    ) -> None:
        self._bridge = bridge
        self._guardian = guardian
        self._state_provider = state_provider or self._default_state_provider
        self._position_size = float(position_size)
        self._last_evaluation: dict[str, Any] = {}

    def _default_state_provider(self) -> dict[str, Any]:
        snap = self._bridge.get_state().get("risk_snapshot", {})
        return state_from_bridge_snapshot(snap)

    @property
    def last_evaluation(self) -> dict[str, Any]:
        return deepcopy(self._last_evaluation)

    def reset(self) -> None:
        if hasattr(self._bridge, "reset"):
            self._bridge.reset()

    def process_signal(
        self,
        signal: int,
        price: float,
        timestamp: str | pd.Timestamp,
    ) -> dict[str, Any]:
        state = self._state_provider()
        evaluation = self._guardian.evaluate(
            state,
            {
                "signal": int(signal),
                "risk": {"position_size": self._position_size},
            },
        )
        self._last_evaluation = evaluation
        approved = int(evaluation["approved_signal"])
        entry = self._bridge.process_signal(approved, price, timestamp)
        entry["guardian"] = deepcopy(evaluation)
        entry["raw_signal_before_guardian"] = int(signal)
        return entry

    def get_state(self) -> dict[str, Any]:
        state = self._bridge.get_state()
        state["guardian"] = self._guardian.get_state()
        state["last_guardian_evaluation"] = deepcopy(self._last_evaluation)
        return state

    def __getattr__(self, name: str) -> Any:
        return getattr(self._bridge, name)


class GuardedPaperTradingEngine:
    """Envolve ``PaperTradingEngine`` — filtra ``on_signal`` antes da execução."""

    def __init__(
        self,
        paper: Any,
        guardian: RiskGuardianV1,
        position_size: float | None = None,
    ) -> None:
        self._paper = paper
        self._guardian = guardian
        st = paper.get_state() if hasattr(paper, "get_state") else {}
        units = float(st.get("position_units", 1.0)) if st else 1.0
        self._position_size = float(position_size if position_size is not None else units)
        self._last_evaluation: dict[str, Any] = {}

    def _sync_guardian_after_trade(self, paper_state: dict[str, Any]) -> None:
        trades = paper_state.get("trades", [])
        if not trades:
            return
        last = trades[-1]
        self._guardian.update_state({
            "pnl": float(last.get("trade_pnl", 0.0)),
            "current_drawdown": float(paper_state.get("current_drawdown", 0.0)),
            "exposure": abs(float(paper_state.get("position", 0)))
                * float(paper_state.get("position_units", 1.0)),
            "position": int(paper_state.get("position", 0)),
            "is_loss": float(last.get("trade_pnl", 0.0)) < 0,
        })

    def on_signal(self, signal: int) -> dict[str, Any]:
        paper_state = self._paper.get_state()
        evaluation = self._guardian.evaluate(
            state_from_paper(paper_state),
            {
                "signal": int(signal),
                "risk": {"position_size": self._position_size},
            },
        )
        self._last_evaluation = evaluation
        return self._paper.on_signal(int(evaluation["approved_signal"]))

    def update_position(self, price: float) -> dict[str, Any]:
        state = self._paper.update_position(price)
        self._sync_guardian_after_trade(state)
        return state

    def close_position(self, reason: str, price: float | None = None) -> dict[str, Any]:
        state = self._paper.close_position(reason, price=price)
        self._sync_guardian_after_trade(state)
        return state

    def initialize_state(self) -> dict[str, Any]:
        self._guardian.reset()
        return self._paper.initialize_state()

    def get_state(self) -> dict[str, Any]:
        state = self._paper.get_state()
        state["guardian"] = self._guardian.get_state()
        state["last_guardian_evaluation"] = deepcopy(self._last_evaluation)
        return state

    def __getattr__(self, name: str) -> Any:
        return getattr(self._paper, name)


def guarded_run_decision_pipeline(
    guardian: RiskGuardianV1,
    df: pd.DataFrame,
    state: dict[str, Any] | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """
    Executa ``run_decision_pipeline`` e aplica guardian no último sinal (causal).
    """
    from microstructure.core.decision_engine import run_decision_pipeline

    decision = run_decision_pipeline(df, apply_risk=False, **kwargs)
    signals = decision["signals"].astype(int).copy()
    if len(signals) == 0:
        return decision

    last_idx = signals.index[-1]
    proposed = int(signals.loc[last_idx])
    out = guardian.evaluate(state or guardian.get_state(), {"signal": proposed})
    signals.loc[last_idx] = int(out["approved_signal"])

    result = dict(decision)
    result["signals"] = signals
    result["guardian_last"] = out
    return result


def apply_guardian_to_decision(
    guardian: RiskGuardianV1,
    decision: dict[str, Any],
    state: dict[str, Any] | None = None,
    bar_index: int = -1,
) -> dict[str, Any]:
    """Filtra um índice da série de sinais do decision engine."""
    signals = decision["signals"].astype(int).copy()
    idx = signals.index[bar_index]
    proposed = int(signals.loc[idx])
    out = guardian.evaluate(state or guardian.get_state(), {"signal": proposed})
    signals.loc[idx] = int(out["approved_signal"])

    result = dict(decision)
    result["signals"] = signals
    result["guardian_last"] = out
    return result
