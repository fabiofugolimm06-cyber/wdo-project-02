"""
microstructure/risk/risk_guardian_v1.py — circuit breaker global (v1).
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

_VALID_SIGNALS = frozenset({-1, 0, 1})


def _extract_signal(proposed_signal: int | dict[str, Any]) -> int:
    if isinstance(proposed_signal, dict):
        if "signal" not in proposed_signal:
            raise ValueError("proposed_signal: dict deve conter 'signal'.")
        return int(proposed_signal["signal"])
    return int(proposed_signal)


def _extract_position_size(proposed_signal: int | dict[str, Any]) -> float | None:
    if not isinstance(proposed_signal, dict):
        return None
    risk = proposed_signal.get("risk")
    if isinstance(risk, dict) and "position_size" in risk:
        return float(risk["position_size"])
    if "position_size" in proposed_signal:
        return float(proposed_signal["position_size"])
    return None


def _default_runtime_state() -> dict[str, Any]:
    return {
        "daily_pnl": 0.0,
        "current_drawdown": 0.0,
        "consecutive_losses": 0,
        "exposure": 0.0,
        "halted": False,
        "kill_switch": False,
        "cooldown_remaining": 0,
    }


class RiskGuardianV1:
    """
    Proteção global independente de estratégia (fail-safe: dúvida → bloqueia).

    Limites típicos:
    - ``max_daily_loss``: piso de PnL diário (ex.: ``-150.0``)
    - ``max_drawdown``: piso de drawdown (ex.: ``-0.10``)
    - ``max_consecutive_losses``: perdas seguidas antes do cooldown
    - ``max_position_exposure``: exposição máxima (unidades absolutas)
    - ``cooldown_after_loss``: barras de pausa após streak
    """

    def __init__(
        self,
        max_daily_loss: float = -150.0,
        max_drawdown: float = -0.10,
        max_consecutive_losses: int = 3,
        max_position_exposure: float = 1.0,
        cooldown_after_loss: int = 5,
    ) -> None:
        if max_daily_loss > 0:
            raise ValueError(
                f"RiskGuardianV1: max_daily_loss deve ser <= 0, got {max_daily_loss}."
            )
        if max_drawdown > 0:
            raise ValueError(
                f"RiskGuardianV1: max_drawdown deve ser <= 0, got {max_drawdown}."
            )
        if max_consecutive_losses < 1:
            raise ValueError(
                "RiskGuardianV1: max_consecutive_losses deve ser >= 1."
            )
        if max_position_exposure <= 0:
            raise ValueError(
                "RiskGuardianV1: max_position_exposure deve ser > 0."
            )
        if cooldown_after_loss < 0:
            raise ValueError(
                "RiskGuardianV1: cooldown_after_loss deve ser >= 0."
            )

        self._max_daily_loss = float(max_daily_loss)
        self._max_drawdown = float(max_drawdown)
        self._max_consecutive_losses = int(max_consecutive_losses)
        self._max_position_exposure = float(max_position_exposure)
        self._cooldown_after_loss = int(cooldown_after_loss)
        self._runtime = _default_runtime_state()
        self._audit_log: list[dict[str, Any]] = []

    def reset(self) -> None:
        """Reinicia estado interno e log de auditoria."""
        self._runtime = _default_runtime_state()
        self._audit_log = []

    def get_state(self) -> dict[str, Any]:
        return deepcopy(self._runtime)

    def get_audit_log(self) -> list[dict[str, Any]]:
        return deepcopy(self._audit_log)

    def force_stop(self, reason: str = "manual_kill_switch") -> None:
        """Kill switch manual — HALT total até ``reset()``."""
        self._runtime["kill_switch"] = True
        self._runtime["halted"] = True
        self._append_audit(0, reason, blocked=True, halted=True)

    def _append_audit(
        self,
        approved_signal: int,
        reason: str,
        *,
        blocked: bool,
        halted: bool | None = None,
        proposed_signal: int | None = None,
    ) -> None:
        self._audit_log.append({
            "approved_signal": int(approved_signal),
            "proposed_signal": proposed_signal,
            "reason": str(reason),
            "blocked": bool(blocked),
            "halted": self._runtime["halted"] if halted is None else halted,
            "cooldown_remaining": int(self._runtime["cooldown_remaining"]),
            "daily_pnl": float(self._runtime["daily_pnl"]),
            "current_drawdown": float(self._runtime["current_drawdown"]),
            "consecutive_losses": int(self._runtime["consecutive_losses"]),
            "exposure": float(self._runtime["exposure"]),
        })

    def _tick_cooldown(self) -> None:
        if self._runtime["cooldown_remaining"] > 0:
            self._runtime["cooldown_remaining"] -= 1

    def _merge_state(self, state: dict[str, Any] | None) -> dict[str, Any]:
        merged = deepcopy(self._runtime)
        if not state:
            return merged
        for key in (
            "daily_pnl",
            "current_drawdown",
            "consecutive_losses",
            "exposure",
            "halted",
            "kill_switch",
            "cooldown_remaining",
        ):
            if key in state and state[key] is not None:
                merged[key] = state[key]
        return merged

    def _exposure_exceeded(
        self,
        merged: dict[str, Any],
        sig: int,
        proposed_size: float | None,
    ) -> bool:
        current = abs(float(merged.get("exposure", 0.0)))
        if sig == 0:
            return False
        add = abs(proposed_size) if proposed_size is not None else 1.0
        position = int(merged.get("position", 0))
        if current >= self._max_position_exposure:
            if position == 0 or position == sig:
                return True
        if current == 0:
            return add > self._max_position_exposure
        if position == sig:
            return (current + add) > self._max_position_exposure
        return add > self._max_position_exposure

    def evaluate(
        self,
        state: dict[str, Any] | None,
        proposed_signal: int | dict[str, Any],
    ) -> dict[str, Any]:
        """
        Avalia sinal proposto; retorna sinal aprovado (ou 0) e motivo auditável.
        """
        self._tick_cooldown()

        try:
            sig = _extract_signal(proposed_signal)
        except (TypeError, ValueError):
            return self._block(
                0,
                "fail_safe_invalid_proposed_signal",
                proposed_signal=None,
                state=state,
            )

        proposed_size = _extract_position_size(proposed_signal)
        merged = self._merge_state(state)

        if sig not in _VALID_SIGNALS:
            return self._block(
                0,
                "fail_safe_invalid_signal_value",
                proposed_signal=sig,
                state=state,
            )

        if merged.get("kill_switch") or self._runtime["kill_switch"]:
            if sig != 0:
                return self._block(
                    0,
                    "kill_switch_active",
                    proposed_signal=sig,
                    state=state,
                )

        if merged.get("halted") or self._runtime["halted"]:
            if sig != 0:
                return self._block(
                    0,
                    "halt_active",
                    proposed_signal=sig,
                    state=state,
                )

        if sig == 0:
            return self._allow(0, "flat_allowed", proposed_signal=sig, state=state)

        if int(merged.get("cooldown_remaining", 0)) > 0:
            return self._block(
                0,
                "cooldown_after_loss_streak",
                proposed_signal=sig,
                state=state,
            )

        daily_pnl = float(merged.get("daily_pnl", 0.0))
        if daily_pnl <= self._max_daily_loss:
            self._runtime["halted"] = True
            return self._block(
                0,
                "max_daily_loss_breached",
                proposed_signal=sig,
                state=state,
                halted=True,
            )

        drawdown = float(merged.get("current_drawdown", 0.0))
        if drawdown > 0:
            return self._block(
                0,
                "fail_safe_invalid_drawdown",
                proposed_signal=sig,
                state=state,
            )

        if drawdown <= self._max_drawdown:
            self._runtime["halted"] = True
            return self._block(
                0,
                "max_drawdown_halt",
                proposed_signal=sig,
                state=state,
                halted=True,
            )

        if self._exposure_exceeded(merged, sig, proposed_size):
            return self._block(
                0,
                "max_position_exposure_exceeded",
                proposed_signal=sig,
                state=state,
            )

        return self._allow(sig, "approved", proposed_signal=sig, state=state)

    def _allow(
        self,
        approved: int,
        reason: str,
        *,
        proposed_signal: int | None,
        state: dict[str, Any] | None,
    ) -> dict[str, Any]:
        self._sync_runtime_from_external(state)
        self._append_audit(
            approved,
            reason,
            blocked=False,
            proposed_signal=proposed_signal,
        )
        return {
            "approved_signal": int(approved),
            "reason": reason,
            "blocked": False,
            "halted": bool(self._runtime["halted"]),
            "trading_allowed": True,
        }

    def _block(
        self,
        approved: int,
        reason: str,
        *,
        proposed_signal: int | None,
        state: dict[str, Any] | None,
        halted: bool | None = None,
    ) -> dict[str, Any]:
        self._sync_runtime_from_external(state)
        if halted is not None:
            self._runtime["halted"] = halted
        self._append_audit(
            approved,
            reason,
            blocked=True,
            halted=halted,
            proposed_signal=proposed_signal,
        )
        return {
            "approved_signal": int(approved),
            "reason": reason,
            "blocked": True,
            "halted": bool(self._runtime["halted"]),
            "trading_allowed": False,
        }

    def _sync_runtime_from_external(self, state: dict[str, Any] | None) -> None:
        if not state:
            return
        for key in (
            "daily_pnl",
            "current_drawdown",
            "consecutive_losses",
            "exposure",
            "halted",
            "kill_switch",
            "cooldown_remaining",
        ):
            if key in state:
                self._runtime[key] = state[key]

    def update_state(self, trade_result: dict[str, Any]) -> dict[str, Any]:
        """
        Atualiza PnL diário, streak de perdas, drawdown e exposição.

        ``trade_result`` aceita, entre outros:
        ``pnl``, ``daily_pnl``, ``current_drawdown``, ``exposure``,
        ``is_loss``, ``position``.
        """
        if not isinstance(trade_result, dict):
            raise ValueError("update_state: trade_result deve ser dict.")

        if "daily_pnl" in trade_result:
            self._runtime["daily_pnl"] = float(trade_result["daily_pnl"])
        elif "pnl" in trade_result:
            self._runtime["daily_pnl"] += float(trade_result["pnl"])

        if "current_drawdown" in trade_result:
            self._runtime["current_drawdown"] = float(trade_result["current_drawdown"])

        if "exposure" in trade_result:
            self._runtime["exposure"] = abs(float(trade_result["exposure"]))
        elif "position" in trade_result:
            self._runtime["exposure"] = abs(float(trade_result["position"]))

        is_loss = trade_result.get("is_loss")
        if is_loss is None and "pnl" in trade_result:
            is_loss = float(trade_result["pnl"]) < 0

        if is_loss:
            self._runtime["consecutive_losses"] += 1
            if self._runtime["consecutive_losses"] >= self._max_consecutive_losses:
                self._runtime["cooldown_remaining"] = max(
                    self._runtime["cooldown_remaining"],
                    self._cooldown_after_loss,
                )
        elif is_loss is False:
            self._runtime["consecutive_losses"] = 0

        if self._runtime["daily_pnl"] <= self._max_daily_loss:
            self._runtime["halted"] = True
        if self._runtime["current_drawdown"] <= self._max_drawdown:
            self._runtime["halted"] = True

        return self.get_state()
