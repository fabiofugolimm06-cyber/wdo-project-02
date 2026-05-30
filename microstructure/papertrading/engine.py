"""
microstructure/papertrading/engine.py — paper trading com estado persistente (v1).
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from microstructure.risk.risk_engine import (
    check_daily_loss_limit,
    check_max_drawdown,
    risk_filter,
)
from microstructure.strategy_config import get_default_config

_VALID_SIGNALS = {-1, 0, 1}


def _signed_return_pct(price: float, entry: float, position: int) -> float:
    if position > 0:
        return price / entry - 1.0
    return entry / price - 1.0


def _apply_slippage(
    price: float,
    position: int,
    slippage: float,
    is_entry: bool,
) -> float:
    """Slippage desfavorável na entrada/saída (fração do preço)."""
    if position > 0:
        return price * (1.0 + slippage) if is_entry else price * (1.0 - slippage)
    if position < 0:
        return price * (1.0 - slippage) if is_entry else price * (1.0 + slippage)
    return price


class PaperTradingEngine:
    """
    Simulação de trading em papel com posição aberta, PnL e custos.

    Integra Risk Engine (filtro de sinais) e parâmetros de Strategy Config
    (slippage, custo, stop/take profit).
    """

    def __init__(
        self,
        initial_capital: float = 100_000.0,
        strategy_config: dict[str, Any] | None = None,
        daily_loss_limit: float = -1_500.0,
        max_drawdown_limit: float = -0.10,
        risk_per_trade: float | None = None,
    ) -> None:
        if initial_capital <= 0:
            raise ValueError(
                f"PaperTradingEngine: initial_capital deve ser > 0, got {initial_capital}."
            )

        self._initial_capital = float(initial_capital)
        self._config = strategy_config or get_default_config("paper_trading")
        params = self._config["parameters"]
        backtest = params["backtest"]
        execution = params["execution"]

        self._cost_per_trade = float(backtest["cost_per_trade"])
        self._slippage = float(backtest["slippage"])
        self._stop_loss = float(backtest["stop_loss"])
        self._take_profit = float(backtest["take_profit"])
        self._position_units = float(execution["position_size"])
        self._daily_loss_limit = float(daily_loss_limit)
        self._max_drawdown_limit = float(max_drawdown_limit)
        self._risk_per_trade = risk_per_trade

        self._state: dict[str, Any] | None = None

    def initialize_state(self) -> dict[str, Any]:
        """Reinicia estado da sessão paper."""
        self._state = {
            "position": 0,
            "entry_price": None,
            "current_pnl": 0.0,
            "realized_pnl": 0.0,
            "unrealized_pnl": 0.0,
            "capital": self._initial_capital,
            "equity_peak": self._initial_capital,
            "current_drawdown": 0.0,
            "trades": [],
            "last_price": None,
            "position_units": self._position_units,
            "trading_enabled": True,
            "bar_index": 0,
            "total_costs": 0.0,
        }
        return self.get_state()

    def _require_state(self) -> dict[str, Any]:
        if self._state is None:
            raise RuntimeError(
                "PaperTradingEngine: chame initialize_state() antes de operar."
            )
        return self._state

    def _equity(self, state: dict[str, Any]) -> float:
        return state["capital"] + state["realized_pnl"] + state["unrealized_pnl"]

    def _update_drawdown(self, state: dict[str, Any]) -> None:
        equity = self._equity(state)
        if equity > state["equity_peak"]:
            state["equity_peak"] = equity
        if state["equity_peak"] > 0:
            state["current_drawdown"] = equity / state["equity_peak"] - 1.0
        else:
            state["current_drawdown"] = 0.0

    def _risk_allowed(self, state: dict[str, Any]) -> bool:
        daily_ok = check_daily_loss_limit(
            state["realized_pnl"] + state["unrealized_pnl"],
            self._daily_loss_limit,
        )["risk_allowed"]
        dd_ok = check_max_drawdown(
            state["current_drawdown"],
            self._max_drawdown_limit,
        )["risk_allowed"]
        return daily_ok and dd_ok

    def _charge_cost(self, state: dict[str, Any]) -> None:
        cost = state["capital"] * self._cost_per_trade
        state["realized_pnl"] -= cost
        state["total_costs"] += cost

    def close_position(self, reason: str, price: float | None = None) -> dict[str, Any]:
        """Fecha posição aberta e registra trade."""
        state = self._require_state()
        if state["position"] == 0:
            raise ValueError("close_position: nenhuma posição aberta.")

        px = float(price if price is not None else state["last_price"])
        if px <= 0:
            raise ValueError(f"close_position: preço inválido {px}.")

        pos = int(state["position"])
        entry = float(state["entry_price"])
        exit_px = _apply_slippage(px, pos, self._slippage, is_entry=False)
        gross_pct = _signed_return_pct(exit_px, entry, pos)
        notional = state["capital"] * state["position_units"]
        trade_pnl = notional * gross_pct

        state["realized_pnl"] += trade_pnl
        self._charge_cost(state)

        state["trades"].append({
            "entry_price": entry,
            "exit_price": exit_px,
            "position": pos,
            "trade_pnl": float(trade_pnl),
            "return_pct": float(gross_pct),
            "reason": reason,
            "bar_index": state["bar_index"],
        })

        state["position"] = 0
        state["entry_price"] = None
        state["unrealized_pnl"] = 0.0
        state["current_pnl"] = state["realized_pnl"]
        self._update_drawdown(state)
        state["trading_enabled"] = self._risk_allowed(state)
        return self.get_state()

    def _open_position(self, signal: int, price: float) -> None:
        state = self._require_state()
        if signal == 0:
            return
        entry_px = _apply_slippage(price, signal, self._slippage, is_entry=True)
        state["position"] = int(signal)
        state["entry_price"] = float(entry_px)
        self._charge_cost(state)
        state["unrealized_pnl"] = 0.0

    def update_position(self, price: float) -> dict[str, Any]:
        """
        Atualiza PnL mark-to-market; aplica stop/take profit se configurado.
        """
        state = self._require_state()
        px = float(price)
        if px <= 0:
            raise ValueError(f"update_position: preço inválido {px}.")

        state["last_price"] = px
        state["bar_index"] += 1

        if state["position"] != 0 and state["entry_price"] is not None:
            pos = int(state["position"])
            entry = float(state["entry_price"])
            gross_pct = _signed_return_pct(px, entry, pos)

            if gross_pct <= -self._stop_loss:
                self.close_position("stop_loss", price=px)
                state = self._require_state()
            elif gross_pct >= self._take_profit:
                self.close_position("take_profit", price=px)
                state = self._require_state()
            else:
                notional = state["capital"] * state["position_units"]
                state["unrealized_pnl"] = notional * gross_pct

        state["current_pnl"] = state["realized_pnl"] + state["unrealized_pnl"]
        self._update_drawdown(state)
        state["trading_enabled"] = self._risk_allowed(state)
        return self.get_state()

    def on_signal(self, signal: int) -> dict[str, Any]:
        """
        Processa sinal {-1, 0, 1} com Risk Engine e gestão de posição.
        """
        state = self._require_state()
        sig = int(signal)
        if sig not in _VALID_SIGNALS:
            raise ValueError(
                f"on_signal: sinal deve ser -1, 0 ou 1, got {signal}."
            )

        allow = self._risk_allowed(state)
        filtered = risk_filter(
            [sig],
            allow_trading=allow,
        )
        sig = int(filtered["signals"][0])
        state["trading_enabled"] = filtered["trading_enabled"]

        px = state["last_price"]
        if px is None:
            if sig != 0:
                raise ValueError(
                    "on_signal: defina last_price via update_position() antes de abrir."
                )
            return self.get_state()

        current = int(state["position"])

        if sig == 0:
            if current != 0:
                self.close_position("signal_flat", price=px)
            return self.get_state()

        if current != 0 and sig != current:
            self.close_position("signal_flip", price=px)

        state = self._require_state()
        if state["position"] == 0 and sig != 0:
            self._open_position(sig, px)
            state = self._require_state()
            notional = state["capital"] * state["position_units"]
            state["unrealized_pnl"] = notional * _signed_return_pct(
                px, float(state["entry_price"]), sig
            )

        state["current_pnl"] = state["realized_pnl"] + state["unrealized_pnl"]
        self._update_drawdown(state)
        return self.get_state()

    def get_state(self) -> dict[str, Any]:
        """Retorna cópia do estado atual."""
        state = self._require_state()
        return deepcopy(state)
