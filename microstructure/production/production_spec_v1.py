"""
microstructure/production/production_spec_v1.py — contrato de saída WDO (v1).

Decision Engine → Production Spec → (NTSL / Bridge JSON / API)
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import numpy as np
import pandas as pd

_SYMBOL = "WDO"
_VALID_SIGNALS = frozenset({-1, 0, 1})
_VALID_MODES = frozenset({"signal", "ml", "hybrid"})
_ACTION_MAP = {-1: "SELL", 0: "FLAT", 1: "BUY"}


def _signal_to_action(signal: int) -> str:
    sig = int(signal)
    if sig not in _VALID_SIGNALS:
        raise ValueError(f"ProductionSpecV1: sinal inválido {signal}.")
    return _ACTION_MAP[sig]


def _is_nan(value: Any) -> bool:
    if value is None:
        return False
    try:
        return bool(np.isnan(float(value)))
    except (TypeError, ValueError):
        return False


def _coerce_timestamp(value: Any) -> str:
    if isinstance(value, pd.Timestamp):
        return str(value)
    ts = str(value).strip()
    if not ts:
        raise ValueError("ProductionSpecV1: timestamp vazio.")
    return ts


class ProductionSpecV1:
    """
    Contrato único de exportação para Profit NTSL, bridge V6 e API futura.

    Rule-based, determinístico, sem dependências de ML ou execution_bridge.
    """

    def __init__(
        self,
        symbol: str = _SYMBOL,
        default_mode: str = "signal",
        default_confidence: float = 1.0,
        risk_defaults: dict[str, float] | None = None,
        strategy_config: dict[str, Any] | None = None,
    ) -> None:
        if default_mode not in _VALID_MODES:
            raise ValueError(
                f"ProductionSpecV1: default_mode deve ser signal|ml|hybrid, "
                f"got {default_mode!r}."
            )
        if not 0.0 <= float(default_confidence) <= 1.0:
            raise ValueError(
                f"ProductionSpecV1: default_confidence deve estar em [0, 1], "
                f"got {default_confidence}."
            )

        self._symbol = str(symbol).strip() or _SYMBOL
        self._default_mode = default_mode
        self._default_confidence = float(default_confidence)
        self._risk_defaults = self._resolve_risk_defaults(risk_defaults, strategy_config)

    @staticmethod
    def _resolve_risk_defaults(
        risk_defaults: dict[str, float] | None,
        strategy_config: dict[str, Any] | None,
    ) -> dict[str, float]:
        if risk_defaults is not None:
            return {
                "position_size": float(risk_defaults["position_size"]),
                "stop_loss": float(risk_defaults["stop_loss"]),
                "take_profit": float(risk_defaults["take_profit"]),
            }

        stop_loss = 0.01
        take_profit = 0.02
        position_size = 1.0

        if strategy_config is not None:
            params = strategy_config.get("parameters", {})
            bt = params.get("backtest", {})
            ex = params.get("execution", {})
            stop_loss = float(bt.get("stop_loss", stop_loss))
            take_profit = float(bt.get("take_profit", take_profit))
            position_size = float(ex.get("position_size", position_size))

            capital = float(ex.get("initial_capital", 0))
            risk_per_trade = float(bt.get("risk_per_trade", 0.01))
            if capital > 0 and stop_loss > 0:
                from microstructure.risk.risk_engine import calculate_position_size

                position_size = float(
                    calculate_position_size(
                        capital, risk_per_trade, stop_loss
                    )["position_size"]
                )

        return {
            "position_size": position_size,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
        }

    def _build_risk_block(
        self,
        overrides: Mapping[str, Any] | None = None,
    ) -> dict[str, float]:
        risk = dict(self._risk_defaults)
        if overrides:
            for key in ("position_size", "stop_loss", "take_profit"):
                if key in overrides and overrides[key] is not None:
                    risk[key] = float(overrides[key])
        return risk

    def export_signal(
        self,
        signal_row: Mapping[str, Any] | pd.Series,
        **overrides: Any,
    ) -> dict[str, Any]:
        """
        Normaliza uma linha de sinal para o contrato de produção (API-ready).
        """
        row = dict(signal_row)
        merged = {**row, **overrides}

        if "timestamp" not in merged:
            raise ValueError("export_signal: campo 'timestamp' obrigatório.")
        if "signal" not in merged:
            raise ValueError("export_signal: campo 'signal' obrigatório.")

        sig = int(merged["signal"])
        if sig not in _VALID_SIGNALS:
            raise ValueError(f"export_signal: sinal inválido {sig}.")

        mode = str(merged.get("mode", self._default_mode))
        if mode not in _VALID_MODES:
            raise ValueError(f"export_signal: mode inválido {mode!r}.")

        confidence = float(merged.get("confidence", self._default_confidence))
        if _is_nan(confidence) or not 0.0 <= confidence <= 1.0:
            raise ValueError(
                f"export_signal: confidence inválida {confidence}."
            )

        risk_src = merged.get("risk")
        if isinstance(risk_src, Mapping):
            risk = self._build_risk_block(risk_src)
        else:
            risk = self._build_risk_block(merged)

        out = {
            "timestamp": _coerce_timestamp(merged["timestamp"]),
            "symbol": self._symbol,
            "signal": sig,
            "confidence": confidence,
            "mode": mode,
            "risk": risk,
        }

        if "price" in merged and merged["price"] is not None and not _is_nan(merged["price"]):
            out["price"] = float(merged["price"])

        self.validate_output(out)
        return out

    def _normalize_series(
        self,
        signal_series: list[dict[str, Any]] | pd.DataFrame,
    ) -> list[dict[str, Any]]:
        if isinstance(signal_series, pd.DataFrame):
            if len(signal_series) == 0:
                raise ValueError("to_*: signal_series vazio.")
            records: list[dict[str, Any]] = []
            for _, row in signal_series.iterrows():
                records.append(self.export_signal(row))
            return records

        if not signal_series:
            raise ValueError("to_*: signal_series vazio.")

        records = []
        for item in signal_series:
            if "symbol" in item and "risk" in item and isinstance(item.get("risk"), dict):
                self.validate_output(item)
                records.append(dict(item))
            else:
                records.append(self.export_signal(item))

        records.sort(key=lambda r: str(r["timestamp"]))
        return records

    def to_ntsl(self, signal_series: list[dict[str, Any]] | pd.DataFrame) -> str:
        """
        Converte série de sinais em texto NTSL (comentários, rule-based).
        """
        records = self._normalize_series(signal_series)
        lines = [
            f"// WDO Production Spec — NTSL export v1 ({self._symbol})",
            "// TIMESTAMP | SIGNAL | ACTION | PRICE | MODE | CONFIDENCE",
        ]
        for rec in records:
            sig = int(rec["signal"])
            action = _signal_to_action(sig)
            price = rec.get("price")
            price_str = "" if price is None or _is_nan(price) else f"{float(price):.4f}"
            lines.append(
                f"// {rec['timestamp']} | {sig} | {action} | {price_str} | "
                f"{rec['mode']} | {float(rec['confidence']):.4f}"
            )
        lines.append(f"// total_bars={len(records)}")
        return "\n".join(lines) + "\n"

    def to_bridge_json(
        self,
        signal_series: list[dict[str, Any]] | pd.DataFrame,
        *,
        indent: int = 2,
    ) -> str:
        """
        JSON determinístico para execução externa (V6-style), ordenado por timestamp.
        """
        records = self._normalize_series(signal_series)
        packets: list[dict[str, Any]] = []

        for rec in records:
            sig = int(rec["signal"])
            packet: dict[str, Any] = {
                "timestamp": rec["timestamp"],
                "symbol": rec["symbol"],
                "signal": sig,
                "action": _signal_to_action(sig),
                "confidence": float(rec["confidence"]),
                "mode": rec["mode"],
                "risk": dict(rec["risk"]),
            }
            if "price" in rec:
                packet["price"] = float(rec["price"])
            packets.append(packet)

        self.validate_output(packets)
        return json.dumps(packets, indent=indent, ensure_ascii=False)

    def validate_output(
        self,
        output: dict[str, Any] | list[dict[str, Any]],
    ) -> bool:
        """
        Valida contrato: ordem temporal, sem NaN, sinal ∈ {-1,0,1}, risk > 0.
        """
        records = [output] if isinstance(output, dict) else list(output)
        if not records:
            raise ValueError("validate_output: output vazio.")

        last_ts: str | None = None
        required = {"timestamp", "symbol", "signal", "confidence", "mode", "risk"}

        for i, rec in enumerate(records):
            missing = required - set(rec.keys())
            if missing:
                raise ValueError(
                    f"validate_output[{i}]: campos ausentes {sorted(missing)}."
                )

            ts = _coerce_timestamp(rec["timestamp"])
            if last_ts is not None and ts < last_ts:
                raise ValueError(
                    f"validate_output[{i}]: timestamp fora de ordem {ts} < {last_ts}."
                )
            last_ts = ts

            sig = int(rec["signal"])
            if sig not in _VALID_SIGNALS:
                raise ValueError(f"validate_output[{i}]: sinal inválido {sig}.")

            conf = float(rec["confidence"])
            if _is_nan(conf) or not 0.0 <= conf <= 1.0:
                raise ValueError(f"validate_output[{i}]: confidence inválida.")

            mode = str(rec["mode"])
            if mode not in _VALID_MODES:
                raise ValueError(f"validate_output[{i}]: mode inválido {mode!r}.")

            if "price" in rec and rec["price"] is not None:
                px = float(rec["price"])
                if _is_nan(px) or px <= 0:
                    raise ValueError(f"validate_output[{i}]: price inválido.")

            risk = rec["risk"]
            if not isinstance(risk, dict):
                raise ValueError(f"validate_output[{i}]: risk deve ser dict.")

            for key in ("position_size", "stop_loss", "take_profit"):
                if key not in risk:
                    raise ValueError(f"validate_output[{i}]: risk.{key} ausente.")
                val = float(risk[key])
                if _is_nan(val) or val <= 0:
                    raise ValueError(
                        f"validate_output[{i}]: risk.{key} deve ser > 0, got {val}."
                    )

        return True

    def from_dataframe(
        self,
        df: pd.DataFrame,
        *,
        mode: str | None = None,
        confidence_col: str | None = None,
    ) -> list[dict[str, Any]]:
        """Converte DataFrame (timestamp/signal/...) em lista de contratos."""
        if df is None or len(df) == 0:
            raise ValueError("from_dataframe: df vazio.")

        work = df.copy()
        if "timestamp" not in work.columns:
            if isinstance(work.index, pd.DatetimeIndex):
                work["timestamp"] = work.index.astype(str)
            else:
                work["timestamp"] = work.index.astype(str)

        out: list[dict[str, Any]] = []
        for _, row in work.iterrows():
            payload: dict[str, Any] = {
                "timestamp": row["timestamp"],
                "signal": int(row["signal"]),
            }
            if mode is not None:
                payload["mode"] = mode
            if confidence_col and confidence_col in work.columns:
                payload["confidence"] = float(row[confidence_col])
            if "price" in work.columns and not pd.isna(row.get("price")):
                payload["price"] = float(row["price"])
            out.append(self.export_signal(payload))
        return out
