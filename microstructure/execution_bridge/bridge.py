"""
microstructure/execution_bridge/bridge.py — camada unificada de execução (v1).
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Literal

import pandas as pd

from microstructure.execution_bridge.exporters import (
    export_bridge_json,
    export_to_bridge_format,
    export_to_ntsl,
    send_to_execution_layer,
    signal_to_action,
)
from microstructure.papertrading import PaperTradingEngine
from microstructure.risk.risk_engine import (
    check_daily_loss_limit,
    check_max_drawdown,
    risk_filter,
)
from microstructure.strategy_config import get_default_config, validate_strategy_config

ExecutionMode = Literal["paper", "live", "export"]
_VALID_MODES = frozenset({"paper", "live", "export"})
_VALID_SIGNALS = {-1, 0, 1}


class ExecutionBridge:
    """
    Converte sinais em ações operacionais (paper / live stub / export).

    Determinístico: mesma sequência (timestamp, signal, price) → mesmo log.
    """

    def __init__(
        self,
        strategy_config: dict[str, Any] | None = None,
        mode: ExecutionMode = "paper",
        daily_loss_limit: float = -1_500.0,
        max_drawdown_limit: float = -0.10,
    ) -> None:
        if mode not in _VALID_MODES:
            raise ValueError(
                f"ExecutionBridge: mode deve ser paper|live|export, got {mode!r}."
            )

        self._config = strategy_config or get_default_config("execution_bridge")
        validate_strategy_config(self._config)
        self._mode: ExecutionMode = mode
        self._daily_loss_limit = float(daily_loss_limit)
        self._max_drawdown_limit = float(max_drawdown_limit)

        capital = float(self._config["parameters"]["execution"]["initial_capital"])
        self._paper: PaperTradingEngine | None = None
        if mode == "paper":
            self._paper = PaperTradingEngine(
                initial_capital=capital,
                strategy_config=self._config,
                daily_loss_limit=self._daily_loss_limit,
                max_drawdown_limit=self._max_drawdown_limit,
            )

        self._risk_snapshot = {
            "daily_loss_limit": self._daily_loss_limit,
            "max_drawdown_limit": self._max_drawdown_limit,
            "trading_enabled": True,
            "risk_allowed": True,
        }
        self._execution_log: list[dict[str, Any]] = []
        self._live_stub_log: list[dict[str, Any]] = []
        self._last_timestamp: str | None = None
        self._sequence: int = 0

        self.reset()

    def reset(self) -> None:
        """Reinicia log e estado (paper reinicializado se aplicável)."""
        self._execution_log = []
        self._live_stub_log = []
        self._last_timestamp = None
        self._sequence = 0

        if self._paper is not None:
            self._paper.initialize_state()
            self._sync_risk_from_paper()

        self._risk_snapshot["trading_enabled"] = True
        self._risk_snapshot["risk_allowed"] = True

    def _sync_risk_from_paper(self) -> None:
        if self._paper is None:
            return
        ps = self._paper.get_state()
        self._risk_snapshot.update({
            "trading_enabled": bool(ps.get("trading_enabled", True)),
            "risk_allowed": bool(ps.get("trading_enabled", True)),
            "current_pnl": float(ps.get("current_pnl", 0)),
            "current_drawdown": float(ps.get("current_drawdown", 0)),
            "position": int(ps.get("position", 0)),
        })

    def _risk_allowed_standalone(self) -> bool:
        """Risk check quando não há paper (export/live)."""
        pnl = float(self._risk_snapshot.get("current_pnl", 0))
        dd = float(self._risk_snapshot.get("current_drawdown", 0))
        daily_ok = check_daily_loss_limit(pnl, self._daily_loss_limit)["risk_allowed"]
        dd_ok = check_max_drawdown(dd, self._max_drawdown_limit)["risk_allowed"]
        return daily_ok and dd_ok

    def _validate_timestamp(self, timestamp: str | pd.Timestamp) -> str:
        ts = str(timestamp).strip()
        if not ts:
            raise ValueError("process_signal: timestamp vazio.")
        if self._last_timestamp is not None and ts < self._last_timestamp:
            raise ValueError(
                f"process_signal: timestamp fora de ordem {ts} < {self._last_timestamp}."
            )
        self._last_timestamp = ts
        return ts

    def process_signal(
        self,
        signal: int,
        price: float,
        timestamp: str | pd.Timestamp,
    ) -> dict[str, Any]:
        """
        Processa um sinal com preço e timestamp (causal, sem lookahead).
        """
        sig = int(signal)
        if sig not in _VALID_SIGNALS:
            raise ValueError(f"process_signal: sinal inválido {signal}.")

        px = float(price)
        if px <= 0:
            raise ValueError(f"process_signal: preço inválido {price}.")

        ts = self._validate_timestamp(timestamp)
        self._sequence += 1

        if self._paper is not None:
            allow = self._paper.get_state().get("trading_enabled", True)
        else:
            allow = self._risk_allowed_standalone()

        filtered = risk_filter([sig], allow_trading=bool(allow))
        filtered_sig = int(filtered["signals"][0])

        self._risk_snapshot["trading_enabled"] = bool(filtered["trading_enabled"])
        self._risk_snapshot["risk_allowed"] = bool(filtered["risk_allowed"])

        if self._mode == "paper" and self._paper is not None:
            self._paper.update_position(px)
            self._paper.on_signal(filtered_sig)
            self._sync_risk_from_paper()

        action = signal_to_action(filtered_sig)
        entry = {
            "timestamp": ts,
            "signal": filtered_sig,
            "raw_signal": sig,
            "action": action,
            "mode": self._mode,
            "price": px,
            "sequence": self._sequence,
            "risk_allowed": self._risk_snapshot["risk_allowed"],
        }
        self._execution_log.append(entry)

        if self._mode == "live":
            packet = {
                "timestamp": ts,
                "signal": filtered_sig,
                "price": px,
                "risk": deepcopy(self._risk_snapshot),
            }
            stub = send_to_execution_layer(packet)
            self._live_stub_log.append(stub)

        return entry

    def build_signals_df(self) -> pd.DataFrame:
        """DataFrame ordenado para exportadores (derivado do log)."""
        if not self._execution_log:
            raise ValueError("build_signals_df: execution_log vazio.")

        return pd.DataFrame(self._execution_log)[
            ["timestamp", "signal", "price"]
        ].copy()

    def export_ntsl(self) -> str:
        return export_to_ntsl(self.build_signals_df())

    def export_v6_bridge(self) -> list[dict[str, Any]]:
        return export_to_bridge_format(
            self.build_signals_df(),
            risk_snapshot=self._risk_snapshot,
        )

    def export_v6_bridge_json(self) -> str:
        return export_bridge_json(
            self.build_signals_df(),
            risk_snapshot=self._risk_snapshot,
        )

    def get_state(self) -> dict[str, Any]:
        """Estado agregado incluindo execution_log."""
        paper_state = self._paper.get_state() if self._paper else None
        return {
            "mode": self._mode,
            "execution_log": deepcopy(self._execution_log),
            "live_stub_log": deepcopy(self._live_stub_log),
            "risk_snapshot": deepcopy(self._risk_snapshot),
            "paper_state": deepcopy(paper_state) if paper_state else None,
            "sequence": self._sequence,
        }
