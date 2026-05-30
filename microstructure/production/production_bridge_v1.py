"""
microstructure/production/production_bridge_v1.py — camada de saída para produção (v1).

Formatação determinística: NTSL | Bridge JSON | API stub.
Sem lógica de decisão nem dependência de dados de mercado.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any, Literal

import pandas as pd

ProductionBridgeMode = Literal["ntsl", "bridge", "api"]
_VALID_MODES = frozenset({"ntsl", "bridge", "api"})
_VALID_SIGNALS = frozenset({-1, 0, 1})
_SYMBOL_DEFAULT = "WDO"
_ACTION_MAP = {-1: "SELL", 0: "FLAT", 1: "BUY"}

_REQUIRED_TOP = frozenset({"mode", "timestamp", "symbol", "signal", "risk", "execution"})
_REQUIRED_RISK = frozenset({"position_size", "stop_loss", "take_profit"})
_REQUIRED_EXECUTION = frozenset({"ntsl", "bridge_json", "api_payload"})

_DEFAULT_RISK = {
    "position_size": 1.0,
    "stop_loss": 0.01,
    "take_profit": 0.02,
}


def _signal_to_action(signal: int) -> str:
    sig = int(signal)
    if sig not in _VALID_SIGNALS:
        raise ValueError(f"build_production_packet: sinal inválido {signal}.")
    return _ACTION_MAP[sig]


def _coerce_timestamp(value: Any) -> str:
    if isinstance(value, pd.Timestamp):
        return str(value)
    ts = str(value).strip()
    if not ts:
        raise ValueError("metadata: timestamp obrigatório e não vazio.")
    return ts


def _extract_signal(signal: int | Mapping[str, Any]) -> int:
    if isinstance(signal, Mapping):
        if "signal" not in signal:
            raise ValueError("signal dict deve conter chave 'signal'.")
        return int(signal["signal"])
    return int(signal)


def _normalize_risk(metadata: Mapping[str, Any]) -> dict[str, float]:
    risk = metadata.get("risk")
    if isinstance(risk, Mapping):
        out = dict(_DEFAULT_RISK)
        for key in _REQUIRED_RISK:
            if key in risk and risk[key] is not None:
                out[key] = float(risk[key])
        return out
    out = dict(_DEFAULT_RISK)
    for key in _REQUIRED_RISK:
        if key in metadata and metadata[key] is not None:
            out[key] = float(metadata[key])
    return out


def _normalize_metadata(metadata: Mapping[str, Any] | None) -> dict[str, Any]:
    if metadata is None:
        raise ValueError("build_production_packet: metadata obrigatório.")
    meta = dict(metadata)
    if "timestamp" not in meta:
        raise ValueError("metadata: campo 'timestamp' obrigatório.")
    return meta


def _format_ntsl_line(
    timestamp: str,
    sig: int,
    action: str,
    price: float | None,
    risk: dict[str, float],
) -> str:
    price_str = "" if price is None else f"{price:.4f}"
    return (
        f"// {timestamp} | {sig} | {action} | {price_str} | "
        f"pos={risk['position_size']:.4f} | sl={risk['stop_loss']:.4f} | "
        f"tp={risk['take_profit']:.4f}"
    )


def _build_ntsl_execution(
    timestamp: str,
    sig: int,
    action: str,
    price: float | None,
    risk: dict[str, float],
) -> str:
    header = [
        "// WDO Production Bridge — NTSL export v1",
        "// TIMESTAMP | SIGNAL | ACTION | PRICE | RISK",
    ]
    lines = header + [_format_ntsl_line(timestamp, sig, action, price, risk)]
    lines.append("// total_bars=1")
    return "\n".join(lines) + "\n"


def _build_bridge_json_execution(
    timestamp: str,
    symbol: str,
    sig: int,
    action: str,
    price: float | None,
    risk: dict[str, float],
    metadata: Mapping[str, Any],
) -> dict[str, Any]:
    """
    Pacote único compatível com ``export_to_bridge_format`` (ExecutionBridge v1).
    """
    packet: dict[str, Any] = {
        "timestamp": timestamp,
        "signal": sig,
        "action": action,
        "price": None if price is None else float(price),
        "risk": dict(risk),
    }
    if metadata.get("include_symbol", True):
        packet["symbol"] = symbol
    confidence = metadata.get("confidence")
    if confidence is not None:
        packet["confidence"] = float(confidence)
    strategy_mode = metadata.get("strategy_mode") or metadata.get("decision_mode")
    if strategy_mode is not None:
        packet["mode"] = str(strategy_mode)
    return packet


def _build_api_payload_execution(
    timestamp: str,
    symbol: str,
    sig: int,
    action: str,
    price: float | None,
    risk: dict[str, float],
) -> dict[str, Any]:
    """Stub para execução API futura — sem chamada de rede."""
    return {
        "version": "api_v1_stub",
        "status": "not_implemented",
        "message": "API execution layer not connected",
        "endpoint": "/v1/orders/signal",
        "method": "POST",
        "body": {
            "timestamp": timestamp,
            "symbol": symbol,
            "signal": sig,
            "side": action,
            "price": price,
            "risk": dict(risk),
        },
    }


def _build_execution_block(
    mode: ProductionBridgeMode,
    timestamp: str,
    symbol: str,
    sig: int,
    action: str,
    price: float | None,
    risk: dict[str, float],
    metadata: Mapping[str, Any],
) -> dict[str, Any]:
    execution: dict[str, Any] = {
        "ntsl": None,
        "bridge_json": None,
        "api_payload": None,
    }
    if mode == "ntsl":
        execution["ntsl"] = _build_ntsl_execution(
            timestamp, sig, action, price, risk
        )
    elif mode == "bridge":
        execution["bridge_json"] = _build_bridge_json_execution(
            timestamp, symbol, sig, action, price, risk, metadata
        )
    else:
        execution["api_payload"] = _build_api_payload_execution(
            timestamp, symbol, sig, action, price, risk
        )
    return execution


def validate_production_packet(packet: Mapping[str, Any]) -> bool:
    """Valida estrutura obrigatória do pacote de produção."""
    missing = _REQUIRED_TOP - set(packet.keys())
    if missing:
        raise ValueError(
            f"validate_production_packet: campos ausentes {sorted(missing)}."
        )

    mode = str(packet["mode"])
    if mode not in _VALID_MODES:
        raise ValueError(f"validate_production_packet: mode inválido {mode!r}.")

    sig = int(packet["signal"])
    if sig not in _VALID_SIGNALS:
        raise ValueError(f"validate_production_packet: sinal inválido {sig}.")

    risk = packet["risk"]
    if not isinstance(risk, dict):
        raise ValueError("validate_production_packet: risk deve ser dict.")
    for key in _REQUIRED_RISK:
        if key not in risk:
            raise ValueError(f"validate_production_packet: risk.{key} ausente.")
        if float(risk[key]) <= 0:
            raise ValueError(f"validate_production_packet: risk.{key} deve ser > 0.")

    execution = packet["execution"]
    if not isinstance(execution, dict):
        raise ValueError("validate_production_packet: execution deve ser dict.")
    missing_exec = _REQUIRED_EXECUTION - set(execution.keys())
    if missing_exec:
        raise ValueError(
            f"validate_production_packet: execution incompleto {sorted(missing_exec)}."
        )

    if mode == "ntsl":
        if not isinstance(execution["ntsl"], str) or not execution["ntsl"].strip():
            raise ValueError("validate_production_packet: ntsl vazio.")
        if execution["bridge_json"] is not None or execution["api_payload"] is not None:
            raise ValueError(
                "validate_production_packet: mode ntsl só deve preencher ntsl."
            )
    elif mode == "bridge":
        if not isinstance(execution["bridge_json"], dict):
            raise ValueError("validate_production_packet: bridge_json inválido.")
        if execution["ntsl"] is not None or execution["api_payload"] is not None:
            raise ValueError(
                "validate_production_packet: mode bridge só deve preencher bridge_json."
            )
    else:
        if not isinstance(execution["api_payload"], dict):
            raise ValueError("validate_production_packet: api_payload inválido.")
        if execution["ntsl"] is not None or execution["bridge_json"] is not None:
            raise ValueError(
                "validate_production_packet: mode api só deve preencher api_payload."
            )

    return True


def build_production_packet(
    signal: int | Mapping[str, Any],
    metadata: Mapping[str, Any] | None,
    mode: ProductionBridgeMode = "ntsl",
) -> dict[str, Any]:
    """
    Monta pacote padronizado de saída para produção.

    Parameters
    ----------
    signal : int ou dict com ``signal`` ∈ {-1, 0, 1}.
    metadata : ``timestamp`` obrigatório; opcional ``symbol``, ``price``, ``risk``, etc.
    mode : ``ntsl`` | ``bridge`` | ``api``.
    """
    if mode not in _VALID_MODES:
        raise ValueError(
            f"build_production_packet: mode inválido {mode!r}. "
            f"Use: {sorted(_VALID_MODES)}."
        )

    meta = _normalize_metadata(metadata)
    sig = _extract_signal(signal)
    if sig not in _VALID_SIGNALS:
        raise ValueError(f"build_production_packet: sinal inválido {sig}.")

    timestamp = _coerce_timestamp(meta["timestamp"])
    symbol = str(meta.get("symbol", _SYMBOL_DEFAULT)).strip() or _SYMBOL_DEFAULT
    risk = _normalize_risk(meta)
    action = _signal_to_action(sig)

    price = meta.get("price")
    price_f: float | None = None
    if price is not None:
        price_f = float(price)
        if price_f <= 0:
            raise ValueError(f"build_production_packet: price inválido {price_f}.")

    packet: dict[str, Any] = {
        "mode": mode,
        "timestamp": timestamp,
        "symbol": symbol,
        "signal": sig,
        "risk": risk,
        "execution": _build_execution_block(
            mode, timestamp, symbol, sig, action, price_f, risk, meta
        ),
    }

    validate_production_packet(packet)
    return packet


def build_production_packets_ordered(
    items: Sequence[tuple[int | Mapping[str, Any], Mapping[str, Any]]],
    mode: ProductionBridgeMode = "bridge",
) -> list[dict[str, Any]]:
    """
    Gera pacotes ordenados por ``timestamp`` (preserva ordem temporal).
    """
    packets = [
        build_production_packet(sig, meta, mode=mode)
        for sig, meta in items
    ]
    packets.sort(key=lambda p: str(p["timestamp"]))
    last: str | None = None
    for p in packets:
        ts = str(p["timestamp"])
        if last is not None and ts < last:
            raise ValueError(
                f"build_production_packets_ordered: timestamp fora de ordem {ts} < {last}."
            )
        last = ts
    return packets


def packets_to_ntsl_bundle(packets: Sequence[Mapping[str, Any]]) -> str:
    """Concatena vários pacotes NTSL em um único texto ordenado."""
    ntsl_packets = [p for p in packets if str(p.get("mode")) == "ntsl"]
    if not ntsl_packets:
        raise ValueError("packets_to_ntsl_bundle: nenhum pacote mode=ntsl.")

    sorted_pkts = sorted(ntsl_packets, key=lambda p: str(p["timestamp"]))
    lines = [
        "// WDO Production Bridge — NTSL bundle v1",
        "// TIMESTAMP | SIGNAL | ACTION | PRICE | RISK",
    ]
    for pkt in sorted_pkts:
        ex = pkt["execution"]
        text = str(ex["ntsl"])
        for line in text.splitlines():
            if line.startswith("// ") and " | " in line and "total_bars" not in line:
                if line.count("|") >= 3 and "NTSL" not in line and "TIMESTAMP" not in line:
                    lines.append(line)
    lines.append(f"// total_bars={len(sorted_pkts)}")
    return "\n".join(lines) + "\n"
