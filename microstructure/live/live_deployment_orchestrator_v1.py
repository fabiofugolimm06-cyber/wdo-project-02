"""
microstructure/live/live_deployment_orchestrator_v1.py — orquestração de deployment (v1).

EVENT STREAM → DECISION → RISK → PRODUCTION SPEC → EXECUTION → STATE
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable, Iterator, Literal

import pandas as pd

from microstructure.risk.guardian_integration_v1 import (
    state_from_bridge_snapshot,
    state_from_paper,
)

DeploymentMode = Literal["paper", "export", "live", "livesim"]
_VALID_MODES = frozenset({"paper", "export", "live", "livesim"})
_VALID_SIGNALS = frozenset({-1, 0, 1})
_OHLCV_COLS = ("abertura", "alta", "baixa", "fechamento", "volume")
_STATUS_RUNNING = "running"
_STATUS_HALTED = "halted"


def _coerce_timestamp(value: Any) -> pd.Timestamp:
    ts = pd.Timestamp(value)
    if pd.isna(ts):
        raise ValueError("market_bar: timestamp inválido.")
    return ts


class LiveDeploymentOrchestratorV1:
    """
    Orquestrador central bar-by-bar — apenas composição, sem lógica de decisão própria.

    Componentes injetados: ``decision_engine``, ``risk_guardian``,
    ``execution_bridge``, ``production_spec``.
    """

    def __init__(
        self,
        decision_engine: Callable[..., dict[str, Any]],
        risk_guardian: Any,
        execution_bridge: Any,
        production_spec: Any,
        mode: DeploymentMode = "paper",
        decision_mode: str = "signal_only",
        price_col: str = "fechamento",
        production_mode: str = "signal",
        default_confidence: float = 1.0,
    ) -> None:
        if mode not in _VALID_MODES:
            raise ValueError(
                f"LiveDeploymentOrchestratorV1: mode inválido {mode!r}. "
                f"Use: {sorted(_VALID_MODES)}."
            )
        if not callable(decision_engine):
            raise TypeError("decision_engine deve ser callable.")
        if not hasattr(risk_guardian, "evaluate"):
            raise TypeError("risk_guardian deve expor evaluate(state, proposed_signal).")
        if not hasattr(execution_bridge, "process_signal"):
            raise TypeError("execution_bridge deve expor process_signal(signal, price, timestamp).")
        if not hasattr(production_spec, "export_signal"):
            raise TypeError("production_spec deve expor export_signal(signal_row).")

        self._decision_fn = decision_engine
        self._risk_guardian = risk_guardian
        self._execution_bridge = execution_bridge
        self._production_spec = production_spec
        self.mode: DeploymentMode = mode
        self._decision_mode = decision_mode
        self._price_col = price_col
        self._production_mode = production_mode
        self._default_confidence = float(default_confidence)

        self._status = _STATUS_RUNNING
        self._halt_reason: str | None = None
        self._buffer: pd.DataFrame | None = None
        self._last_timestamp: pd.Timestamp | None = None
        self._bar_count = 0
        self._deployment_log: list[dict[str, Any]] = []
        self._livesim_events: list[dict[str, Any]] = []

        self.reset()

    def reset(self) -> None:
        """Reinicia buffer, log e componentes (se expuserem reset)."""
        self._status = _STATUS_RUNNING
        self._halt_reason = None
        self._buffer = None
        self._last_timestamp = None
        self._bar_count = 0
        self._deployment_log = []
        self._livesim_events = []

        if hasattr(self._risk_guardian, "reset"):
            self._risk_guardian.reset()
        if hasattr(self._execution_bridge, "reset"):
            self._execution_bridge.reset()

    def _halt(self, reason: str) -> None:
        self._status = _STATUS_HALTED
        self._halt_reason = str(reason)

    def _build_guardian_state(self) -> dict[str, Any]:
        if not hasattr(self._execution_bridge, "get_state"):
            return self._risk_guardian.get_state()

        snap = self._execution_bridge.get_state()
        paper = snap.get("paper_state")
        if paper:
            return state_from_paper(paper)
        return state_from_bridge_snapshot(snap.get("risk_snapshot", {}))

    def _sync_guardian_from_bridge(self) -> None:
        if not hasattr(self._risk_guardian, "update_state"):
            return
        if not hasattr(self._execution_bridge, "get_state"):
            return
        snap = self._execution_bridge.get_state()
        paper = snap.get("paper_state")
        if not paper:
            return
        trades = paper.get("trades", [])
        if trades:
            last = trades[-1]
            self._risk_guardian.update_state({
                "pnl": float(last.get("trade_pnl", 0.0)),
                "current_drawdown": float(paper.get("current_drawdown", 0.0)),
                "exposure": abs(float(paper.get("position", 0)))
                    * float(paper.get("position_units", 1.0)),
                "position": int(paper.get("position", 0)),
                "is_loss": float(last.get("trade_pnl", 0.0)) < 0,
            })
        else:
            self._risk_guardian.update_state({
                "daily_pnl": float(paper.get("current_pnl", 0.0)),
                "current_drawdown": float(paper.get("current_drawdown", 0.0)),
                "exposure": abs(float(paper.get("position", 0)))
                    * float(paper.get("position_units", 1.0)),
                "position": int(paper.get("position", 0)),
            })

    @staticmethod
    def _normalize_market_bar(market_bar: Any) -> tuple[pd.Timestamp, dict[str, float]]:
        if isinstance(market_bar, pd.Series):
            row = market_bar.to_dict()
            if isinstance(market_bar.name, pd.Timestamp):
                row.setdefault("timestamp", market_bar.name)
            elif market_bar.name is not None:
                row.setdefault("timestamp", market_bar.name)
        elif isinstance(market_bar, dict):
            row = dict(market_bar)
        else:
            raise TypeError(
                "market_bar deve ser dict ou pd.Series com OHLCV."
            )

        if "timestamp" not in row:
            raise ValueError("market_bar: campo 'timestamp' obrigatório.")

        ts = _coerce_timestamp(row["timestamp"])
        ohlcv: dict[str, float] = {}
        for col in _OHLCV_COLS:
            if col not in row:
                raise ValueError(f"market_bar: coluna '{col}' ausente.")
            val = float(row[col])
            if val != val:  # NaN
                raise ValueError(f"market_bar: '{col}' não pode ser NaN.")
            ohlcv[col] = val

        return ts, ohlcv

    def _append_bar(self, ts: pd.Timestamp, ohlcv: dict[str, float]) -> pd.DataFrame:
        row = pd.DataFrame([ohlcv], index=pd.DatetimeIndex([ts]))
        if self._buffer is None:
            self._buffer = row
        else:
            if ts <= self._last_timestamp:
                raise ValueError(
                    f"market_bar: timestamp fora de ordem {ts} <= {self._last_timestamp}."
                )
            self._buffer = pd.concat([self._buffer, row])
        self._last_timestamp = ts
        return self._buffer

    def on_new_market_data(self, market_bar: Any) -> dict[str, Any]:
        """
        Pipeline por evento (bar-by-bar).

        1. decision_engine (slice causal)
        2. risk_guardian
        3. production_spec
        4. execution_bridge (se não bloqueado)
        5. log estruturado
        """
        if self._status == _STATUS_HALTED:
            entry = self._log_entry_halted(market_bar, reason=self._halt_reason or "halted")
            self._deployment_log.append(entry)
            return entry

        try:
            ts, ohlcv = self._normalize_market_bar(market_bar)
            price = float(ohlcv.get(self._price_col, ohlcv["fechamento"]))
            if price <= 0:
                raise ValueError(f"market_bar: preço inválido {price}.")

            slice_df = self._append_bar(ts, ohlcv)
            self._bar_count += 1

            decision = self._decision_fn(
                slice_df,
                mode=self._decision_mode,
                apply_risk=False,
            )
            signals = decision["signals"]
            if len(signals) == 0:
                raise RuntimeError("decision_engine retornou série de sinais vazia.")

            raw_signal = int(signals.iloc[-1])
            if raw_signal not in _VALID_SIGNALS:
                raise ValueError(f"decision_engine: sinal inválido {raw_signal}.")

            guardian_state = self._build_guardian_state()
            risk_block = {"position_size": 1.0}
            defaults = getattr(self._production_spec, "_risk_defaults", None)
            if isinstance(defaults, dict) and "position_size" in defaults:
                risk_block = {"position_size": float(defaults["position_size"])}

            risk_out = self._risk_guardian.evaluate(
                guardian_state,
                {"signal": raw_signal, "risk": risk_block},
            )
            approved = int(risk_out["approved_signal"])
            if approved not in _VALID_SIGNALS:
                self._halt("inconsistent_guardian_signal")
                return self._log_entry_halted(market_bar, reason="inconsistent_guardian_signal")

            prod_row = self._production_spec.export_signal({
                "timestamp": ts,
                "signal": approved,
                "confidence": self._default_confidence,
                "mode": self._production_mode,
                "price": price,
            })

            execution_action: dict[str, Any]
            if risk_out.get("blocked"):
                execution_action = {
                    "status": "skipped",
                    "reason": risk_out.get("reason", "risk_blocked"),
                }
            else:
                execution_action = dict(
                    self._execution_bridge.process_signal(approved, price, ts)
                )
                self._sync_guardian_from_bridge()

            entry = {
                "timestamp": ts,
                "bar_index": self._bar_count - 1,
                "signal": approved,
                "raw_signal": raw_signal,
                "price": price,
                "decision": {
                    "mode": self._decision_mode,
                    "pipeline_mode": decision.get("mode", self._decision_mode),
                    "raw_signal": raw_signal,
                    "model_used": bool(decision.get("model_used", False)),
                },
                "risk_action": deepcopy(risk_out),
                "production": prod_row,
                "execution_action": execution_action,
                "deployment_mode": self.mode,
            }
            self._deployment_log.append(entry)

            if self.mode == "livesim":
                self._livesim_events.append({
                    "type": "bar",
                    "timestamp": str(ts),
                    "bar_index": entry["bar_index"],
                    "payload": {
                        "price": price,
                        "raw_signal": raw_signal,
                        "signal": approved,
                        "risk_blocked": bool(risk_out.get("blocked")),
                        "execution_status": execution_action.get("status", "executed"),
                    },
                })

            return entry

        except Exception as exc:
            self._halt(f"fail_safe_error: {exc}")
            entry = self._log_entry_halted(market_bar, reason=str(exc))
            self._deployment_log.append(entry)
            return entry

    def _log_entry_halted(
        self,
        market_bar: Any,
        reason: str,
    ) -> dict[str, Any]:
        ts_str = None
        try:
            ts, _ = self._normalize_market_bar(market_bar)
            ts_str = ts
        except Exception:
            pass
        return {
            "timestamp": ts_str,
            "bar_index": self._bar_count,
            "signal": 0,
            "raw_signal": 0,
            "price": None,
            "decision": {"status": "halted", "reason": reason},
            "risk_action": {"blocked": True, "reason": reason, "approved_signal": 0},
            "production": None,
            "execution_action": {"status": "skipped", "reason": reason},
            "deployment_mode": self.mode,
            "halted": True,
        }

    def run_stream(
        self,
        data_stream: pd.DataFrame | Iterator[Any],
    ) -> dict[str, Any]:
        """
        Loop principal sobre fluxo temporal (DataFrame ou iterável de barras).
        """
        self.reset()

        if isinstance(data_stream, pd.DataFrame):
            if len(data_stream) == 0:
                raise ValueError("run_stream: DataFrame vazio.")
            if not isinstance(data_stream.index, pd.DatetimeIndex):
                raise TypeError("run_stream: índice deve ser DatetimeIndex.")
            if not data_stream.index.is_monotonic_increasing:
                raise ValueError("run_stream: índice deve ser monotônico crescente.")

            bars = (
                {"timestamp": ts, **data_stream.loc[ts].to_dict()}
                for ts in data_stream.index
            )
        else:
            bars = data_stream

        for bar in bars:
            if self._status == _STATUS_HALTED:
                break
            self.on_new_market_data(bar)

        if self.mode == "livesim":
            self._livesim_events.insert(0, {
                "type": "stream_start",
                "timestamp": None,
                "bar_index": -1,
                "payload": {"bars": self._bar_count},
            })
            self._livesim_events.append({
                "type": "stream_end",
                "timestamp": str(self._last_timestamp) if self._last_timestamp else None,
                "bar_index": self._bar_count - 1,
                "payload": {"bars_processed": self._bar_count},
            })

        return {
            "log": pd.DataFrame(self._deployment_log),
            "state": self.get_state(),
        }

    def get_deployment_log(self) -> pd.DataFrame:
        return pd.DataFrame(self._deployment_log)

    def get_state(self) -> dict[str, Any]:
        """Estado vivo agregado (modo, PnL, posição, risco)."""
        pnl = 0.0
        position = 0
        bridge_state: dict[str, Any] = {}

        if hasattr(self._execution_bridge, "get_state"):
            bridge_state = self._execution_bridge.get_state()
            paper = bridge_state.get("paper_state")
            if paper:
                pnl = float(paper.get("current_pnl", 0.0))
                position = int(paper.get("position", 0))
            else:
                pnl = float(bridge_state.get("risk_snapshot", {}).get("current_pnl", 0.0))
                position = int(bridge_state.get("risk_snapshot", {}).get("position", 0))

        risk_state = (
            self._risk_guardian.get_state()
            if hasattr(self._risk_guardian, "get_state")
            else {}
        )

        out: dict[str, Any] = {
            "mode": self.mode,
            "status": self._status,
            "halt_reason": self._halt_reason,
            "pnl": pnl,
            "positions": position,
            "risk_state": deepcopy(risk_state),
            "bars_processed": self._bar_count,
            "log_entries": len(self._deployment_log),
            "bridge_state": deepcopy(bridge_state),
        }
        if self.mode == "livesim":
            out["livesim_events"] = deepcopy(self._livesim_events)
        return out
