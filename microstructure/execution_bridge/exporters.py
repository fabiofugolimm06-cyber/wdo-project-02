"""
microstructure/execution_bridge/exporters.py — export NTSL, V6 bridge, live stub.
"""

from __future__ import annotations

import json
from typing import Any

import pandas as pd

_VALID_SIGNALS = {-1, 0, 1}
_ACTION_MAP = {-1: "SELL", 0: "FLAT", 1: "BUY"}


def signal_to_action(signal: int) -> str:
    """Converte sinal {-1,0,1} em ação textual."""
    sig = int(signal)
    if sig not in _VALID_SIGNALS:
        raise ValueError(f"signal_to_action: sinal inválido {signal}.")
    return _ACTION_MAP[sig]


def _normalize_signals_df(signals_df: pd.DataFrame) -> pd.DataFrame:
    if signals_df is None or len(signals_df) == 0:
        raise ValueError("export: signals_df vazio.")

    df = signals_df.copy()
    if "signal" not in df.columns:
        raise ValueError("export: coluna 'signal' obrigatória.")

    if "timestamp" not in df.columns:
        if isinstance(df.index, pd.DatetimeIndex):
            df["timestamp"] = df.index.astype(str)
        else:
            df["timestamp"] = df.index.astype(str)

    if "price" not in df.columns:
        df["price"] = None

    for sig in df["signal"].astype(int).unique():
        if int(sig) not in _VALID_SIGNALS:
            raise ValueError(f"export: sinal inválido {sig}.")

    return df.sort_values("timestamp").reset_index(drop=True)


def export_to_ntsl(signals_df: pd.DataFrame) -> str:
    """
    Exporta sinais em texto simples compatível com leitura manual / Profit (NTSL).

    Uma linha por barra: ``TIMESTAMP | SIGNAL | ACTION | PRICE``.
    """
    df = _normalize_signals_df(signals_df)
    lines = [
        "// WDO Execution Bridge — NTSL export v1",
        "// TIMESTAMP | SIGNAL | ACTION | PRICE",
    ]
    for row in df.itertuples(index=False):
        ts = getattr(row, "timestamp", "")
        sig = int(getattr(row, "signal", 0))
        price = getattr(row, "price", None)
        action = signal_to_action(sig)
        price_str = "" if price is None or pd.isna(price) else f"{float(price):.4f}"
        lines.append(f"// {ts} | {sig} | {action} | {price_str}")

    lines.append(f"// total_bars={len(df)}")
    return "\n".join(lines) + "\n"


def export_to_bridge_format(
    signals_df: pd.DataFrame,
    risk_snapshot: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """
    Formato JSON para ponte V6 / automação externa.

    Returns
    -------
    Lista de pacotes ``{timestamp, signal, price, risk}``.
    """
    df = _normalize_signals_df(signals_df)
    risk = risk_snapshot or {}
    packets: list[dict[str, Any]] = []

    for row in df.itertuples(index=False):
        ts = str(getattr(row, "timestamp", ""))
        sig = int(getattr(row, "signal", 0))
        price = getattr(row, "price", None)
        packets.append({
            "timestamp": ts,
            "signal": sig,
            "action": signal_to_action(sig),
            "price": None if price is None or pd.isna(price) else float(price),
            "risk": dict(risk),
        })

    return packets


def export_bridge_json(
    signals_df: pd.DataFrame,
    risk_snapshot: dict[str, Any] | None = None,
) -> str:
    """JSON serializado do formato bridge."""
    return json.dumps(
        export_to_bridge_format(signals_df, risk_snapshot=risk_snapshot),
        indent=2,
        ensure_ascii=False,
    )


def send_to_execution_layer(signal_packet: dict[str, Any]) -> dict[str, Any]:
    """
    Stub de envio live — não executa ordens reais; retorna log estruturado.
    """
    required = {"timestamp", "signal"}
    missing = required - set(signal_packet.keys())
    if missing:
        raise ValueError(
            f"send_to_execution_layer: campos ausentes {sorted(missing)}."
        )

    sig = int(signal_packet["signal"])
    if sig not in _VALID_SIGNALS:
        raise ValueError(f"send_to_execution_layer: sinal inválido {sig}.")

    log_entry = {
        "status": "logged_only",
        "message": "live execution stub — no real order sent",
        "packet": {
            "timestamp": str(signal_packet["timestamp"]),
            "signal": sig,
            "action": signal_to_action(sig),
            "price": signal_packet.get("price"),
            "risk": signal_packet.get("risk", {}),
        },
    }
    return log_entry
