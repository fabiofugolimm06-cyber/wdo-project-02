"""
strategy_neutral_alpha.py
WDO-EVOLVED-QUANT | Fase 2 — NEUTRAL Alpha Strategy
Versão: 1.0 | 27/05/2026

Transforma o sinal NEUTRAL (volume extremo + regime condicional) em
uma estratégia estatisticamente validada com execução real definida.

Componentes
-----------
_compute_atr()            — ATR(14) calculado localmente (sem depender de regime_classifier)
apply_neutral_filter()    — seleciona tier (strict / relaxed / fallback) automaticamente
backtest_events()         — simulação bar-a-bar: ATR stop + take-profit + horizon exit
compute_metrics()         — expectancy, Sharpe, max drawdown, profit factor, hit rate
plot_equity_curve()       — equity curve por fold + curva agregada + drawdown
run_walk_forward()        — sklearn TimeSeriesSplit (expanding window, n_folds configurável)
run_strategy_validation() — entry point chamado pelo pipeline principal

Integração com o pipeline existente
-------------------------------------
Em extreme_event_analysis_v2.py, passo [7/9]:

    from strategy_neutral_alpha import run_strategy_validation
    run_strategy_validation(test, events, OUTPUT_DIR)

Onde `test` é o DataFrame OOS e `events` é a saída de extract_events().
M1 (event_type) e M2 (vol_regime, trend_regime) são preservados via `events`.

Regras de entry / exit
-----------------------
  Entry     : abertura da barra (pos + 1) após o evento — sem look-ahead.
  Direction : LONG  se body_ratio >= 0  |  SHORT se body_ratio < 0.
              (disponível no fechamento da barra de evento)
  Stop-loss : entry ± ATR(14) × ATR_MULTIPLIER
  Take-profit: entry ± ATR(14) × ATR_MULTIPLIER × TP_RATIO  (default 1:1 R/R)
  Hold max  : MAX_HOLD_BARS barras de 1 min após entry.
  Priority  : stop-loss > take-profit > horizon exit.

Sizing    : 1R fixo por trade — calculado via ATR stop.
Cost      : COST_RT = slippage × 2 + comissão + B3 (importado de cost_model).
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.stats import binomtest

# ── Importar custo do modelo central ─────────────────────────────────────────
# Fallback para caso o script seja importado fora do contexto do pipeline.
try:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from cost_model import COMMISSION_PER_CONTRACT, FEES_B3_PER_CONTRACT
except ImportError:  # pragma: no cover
    COMMISSION_PER_CONTRACT = 0.40
    FEES_B3_PER_CONTRACT    = 0.20

warnings.filterwarnings("ignore", category=RuntimeWarning)

# ── Parâmetros da estratégia (documentar, não otimizar) ───────────────────────
ATR_PERIOD        = 14     # período do ATR para sizing e stop
ATR_MULTIPLIER    = 1.5    # stop = ATR × 1.5
TP_RATIO          = 1.0    # TP = stop × 1.0  → risco:ganho 1:1
MAX_HOLD_BARS     = 15     # horizonte máximo de holding (barras de 1 min)
SLIPPAGE_EXTREME  = 1.0    # slippage em pts por lado (volume extremo)
COST_RT           = (2 * SLIPPAGE_EXTREME) + COMMISSION_PER_CONTRACT + FEES_B3_PER_CONTRACT
POINT_VALUE       = 10.0   # R$/ponto WDO
MIN_EVENTS_TOTAL  = 4      # mínimo de eventos para aceitar um fold

# Momentum adaptativo: percentil de volume_rel que define "alta intensidade"
MOMENTUM_PCT_THR  = 60     # percentil 60 do vol_rel dos eventos NEUTRAL

SEP = "═" * 62
SEP2 = "─" * 62


# ══════════════════════════════════════════════════════════════════════════════
# 1. ATR LOCAL
# ══════════════════════════════════════════════════════════════════════════════

def _compute_atr(df: pd.DataFrame, period: int = ATR_PERIOD) -> pd.Series:
    """
    ATR(period) calculado internamente sem depender de regime_classifier.
    Usa nomes de coluna em português do pipeline WDO.
    """
    prev_close = df["fechamento"].shift(1)
    tr = pd.concat(
        [
            df["máxima"] - df["mínima"],
            (df["máxima"] - prev_close).abs(),
            (df["mínima"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.rolling(period, min_periods=period).mean()


# ══════════════════════════════════════════════════════════════════════════════
# 2. FILTER TIERS (STRICT / RELAXED / FALLBACK)
# ══════════════════════════════════════════════════════════════════════════════

def apply_neutral_filter(
    events: pd.DataFrame,
) -> tuple[pd.DataFrame, str]:
    """
    Seleciona automaticamente o filtro mais restritivo que tenha eventos
    suficientes para ao menos 1 fold útil (>= MIN_EVENTS_TOTAL).

    Retorna (filtered_events, tier_label).

    Tier 1 — strict:
        NEUTRAL + vol ∈ {MID, HIGH} + RANGE + momentum_abs > pct60

    Tier 2 — relaxed:
        NEUTRAL + vol ∈ {MID, HIGH}  (sem filtro de trend)

    Tier 3 — fallback:
        Todos os eventos NEUTRAL (nenhum filtro de regime)
    """
    neutral = events[events["event_direction"] == "NEUTRAL"].copy()

    has_vol   = "vol_regime"   in events.columns
    has_trend = "trend_regime" in events.columns

    # Threshold adaptativo de momentum (percentil 60 do vol_rel dentro dos NEUTRAL)
    vol_threshold = (
        float(neutral["volume_rel"].quantile(MOMENTUM_PCT_THR / 100.0))
        if not neutral.empty and "volume_rel" in neutral.columns
        else 0.0
    )

    def tier1(df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        if has_vol:
            out = out[out["vol_regime"].isin(["HIGH", "MID"])]
        if has_trend:
            out = out[out["trend_regime"] == "RANGE"]
        if "volume_rel" in out.columns and vol_threshold > 0:
            out = out[out["volume_rel"] >= vol_threshold]
        return out

    def tier2(df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        if has_vol:
            out = out[out["vol_regime"].isin(["HIGH", "MID"])]
        return out

    def tier3(df: pd.DataFrame) -> pd.DataFrame:
        return df.copy()

    n1 = len(tier1(neutral))
    n2 = len(tier2(neutral))
    n3 = len(neutral)

    if n1 >= MIN_EVENTS_TOTAL:
        return tier1(neutral), f"Tier 1 — NEUTRAL + vol(H|M) + RANGE + momentum>pct{MOMENTUM_PCT_THR}"
    if n2 >= MIN_EVENTS_TOTAL:
        return tier2(neutral), f"Tier 2 — NEUTRAL + vol(H|M)  [RANGE relaxado]"
    return tier3(neutral),     f"Tier 3 — NEUTRAL  [filtros relaxados | n_tier1={n1} n_tier2={n2}]"


# ══════════════════════════════════════════════════════════════════════════════
# 3. BACKTEST ENGINE
# ══════════════════════════════════════════════════════════════════════════════

def backtest_events(
    df          : pd.DataFrame,
    filtered_ev : pd.DataFrame,
    atr_series  : pd.Series,
) -> pd.DataFrame:
    """
    Simulação bar-a-bar para cada evento em filtered_ev.

    Entry       : abertura da barra (integer_pos + 1)
    Direction   : LONG se body_ratio >= 0 | SHORT se body_ratio < 0
    Stop-loss   : ATR(14) × ATR_MULTIPLIER a partir do entry
    Take-profit : ATR(14) × ATR_MULTIPLIER × TP_RATIO (1:1 default)
    Horizon exit: fechamento da barra (integer_pos + 1 + MAX_HOLD_BARS)
    Priority    : stop > TP > horizon

    Retorna DataFrame com um registro por trade.
    """
    records: list[dict] = []

    for _, ev in filtered_ev.iterrows():
        pos = int(ev["integer_pos"])
        entry_idx = pos + 1

        if entry_idx >= len(df):
            continue

        entry_bar   = df.iloc[entry_idx]
        entry_price = float(entry_bar["abertura"])

        atr_val = float(atr_series.iloc[pos]) if pos < len(atr_series) else float("nan")
        if pd.isna(atr_val) or atr_val <= 0:
            continue

        # Direction from body_ratio sign (available at event close — no look-ahead)
        trade_dir   = 1 if float(ev.get("body_ratio", 0.0)) >= 0 else -1
        stop_dist   = atr_val * ATR_MULTIPLIER
        tp_dist     = stop_dist * TP_RATIO

        if trade_dir == 1:   # LONG
            stop_price = entry_price - stop_dist
            tp_price   = entry_price + tp_dist
        else:                # SHORT
            stop_price = entry_price + stop_dist
            tp_price   = entry_price - tp_dist

        # ── Simulate bar-by-bar ───────────────────────────────────────────────
        end_idx    = min(entry_idx + MAX_HOLD_BARS, len(df) - 1)
        exit_price = float(df.iloc[end_idx]["fechamento"])   # default: horizon exit
        exit_type  = "HORIZON"

        for i in range(entry_idx, end_idx + 1):
            bar_low  = float(df.iloc[i]["mínima"])
            bar_high = float(df.iloc[i]["máxima"])

            if trade_dir == 1:   # LONG: check stop first (conservative)
                if bar_low <= stop_price:
                    exit_price, exit_type = stop_price, "STOP"
                    break
                if bar_high >= tp_price:
                    exit_price, exit_type = tp_price, "TP"
                    break
            else:                # SHORT: check stop first
                if bar_high >= stop_price:
                    exit_price, exit_type = stop_price, "STOP"
                    break
                if bar_low <= tp_price:
                    exit_price, exit_type = tp_price, "TP"
                    break

        # ── P&L ──────────────────────────────────────────────────────────────
        raw_pts = (exit_price - entry_price) * trade_dir
        net_pts = raw_pts - COST_RT
        net_brl = net_pts * POINT_VALUE

        records.append({
            "event_time"  : ev["datetime"],
            "direction"   : "LONG" if trade_dir == 1 else "SHORT",
            "vol_regime"  : ev.get("vol_regime",   "UNKNOWN"),
            "trend_regime": ev.get("trend_regime", "UNKNOWN"),
            "entry_price" : entry_price,
            "exit_price"  : exit_price,
            "exit_type"   : exit_type,
            "atr_val"     : round(atr_val, 4),
            "stop_dist"   : round(stop_dist, 4),
            "raw_pts"     : round(raw_pts, 4),
            "net_pts"     : round(net_pts, 4),
            "net_brl"     : round(net_brl, 2),
            "win"         : net_pts > 0,
        })

    return pd.DataFrame(records)


# ══════════════════════════════════════════════════════════════════════════════
# 4. MÉTRICAS DE PERFORMANCE
# ══════════════════════════════════════════════════════════════════════════════

def compute_metrics(trades: pd.DataFrame) -> dict:
    """
    Calcula métricas completas de performance para uma série de trades.

    Retorna dict com:
      n, hit_rate, expectancy (pts), expectancy_brl (R$),
      sharpe, max_dd_pts, profit_factor, p_value (binomial), cum_pnl (array).
    """
    if trades.empty or len(trades) < 3:
        return {"n": len(trades), "insufficient": True}

    pnl   = trades["net_pts"].values.astype(float)
    wins  = trades["win"].values.astype(bool)

    hit_rate    = float(wins.mean())
    expectancy  = float(pnl.mean())
    exp_brl     = expectancy * POINT_VALUE
    pnl_std     = float(pnl.std(ddof=1)) if len(pnl) > 1 else 0.0
    sharpe      = expectancy / (pnl_std + 1e-9)

    # Max drawdown em pontos
    cum_pnl  = np.cumsum(pnl)
    peak     = np.maximum.accumulate(cum_pnl)
    max_dd   = float((peak - cum_pnl).max())

    # Profit factor
    gain_sum = float(pnl[pnl > 0].sum()) if (pnl > 0).any() else 0.0
    loss_sum = float(abs(pnl[pnl < 0].sum())) if (pnl < 0).any() else 1e-9
    pf       = gain_sum / (loss_sum + 1e-9)

    # Binomial p-value (win rate > 50%?)
    n_wins = int(wins.sum())
    p_val  = float(binomtest(n_wins, len(wins), 0.5, alternative="greater").pvalue)

    # Exit type distribution
    if "exit_type" in trades.columns:
        exit_dist = trades["exit_type"].value_counts().to_dict()
    else:
        exit_dist = {}

    return {
        "n"             : len(trades),
        "hit_rate"      : hit_rate,
        "expectancy"    : expectancy,
        "expectancy_brl": exp_brl,
        "sharpe"        : sharpe,
        "max_dd_pts"    : max_dd,
        "profit_factor" : pf,
        "p_value"       : p_val,
        "cum_pnl"       : cum_pnl,
        "exit_dist"     : exit_dist,
        "insufficient"  : False,
    }


def _print_metrics(label: str, m: dict) -> None:
    """Imprime bloco de métricas formatado para um split."""
    if m.get("insufficient"):
        print(f"  {label}: n={m['n']} — dados insuficientes (mínimo 3 trades)")
        return

    print(f"  {label}  (n={m['n']} trades)")
    print(f"    hit rate      : {m['hit_rate']:.1%}")
    print(f"    expectancy    : {m['expectancy']:+.4f} pts  "
          f"({m['expectancy_brl']:+.2f} R$)")
    print(f"    Sharpe (simpl): {m['sharpe']:+.3f}")
    print(f"    max drawdown  : {m['max_dd_pts']:.2f} pts")
    print(f"    profit factor : {m['profit_factor']:.2f}")
    print(f"    p-value binom : {m['p_value']:.4f}"
          f"{'  ← sig. 5%' if m['p_value'] < 0.05 else ''}")
    if m.get("exit_dist"):
        print(f"    exit types    : {m['exit_dist']}")


# ══════════════════════════════════════════════════════════════════════════════
# 5. EQUITY CURVE PLOT
# ══════════════════════════════════════════════════════════════════════════════

def plot_equity_curve(
    fold_trades : list[tuple[int, pd.DataFrame]],
    output_path : Path,
) -> None:
    """
    Gera dois subplots:
      Esquerda : equity curve separada por fold
      Direita  : equity curve agregada (OOS) + área de drawdown
    """
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    palette = plt.cm.viridis(np.linspace(0.15, 0.85, len(fold_trades)))

    # ── Esquerda: por fold ────────────────────────────────────────────────────
    ax1 = axes[0]
    for i, (fold_id, trades) in enumerate(fold_trades):
        if trades.empty:
            continue
        cum = trades["net_pts"].cumsum().values
        ax1.plot(range(len(cum)), cum, color=palette[i],
                 linewidth=2, label=f"Fold {fold_id} (n={len(trades)})")

    ax1.axhline(0, color="black", linewidth=0.8, linestyle="--")
    ax1.set_title("Equity Curve por Fold (OOS)")
    ax1.set_xlabel("Trade #")
    ax1.set_ylabel("Cumulative PnL (pts)")
    ax1.legend(fontsize=9)
    ax1.grid(True, alpha=0.25)

    # ── Direita: agregada + drawdown ──────────────────────────────────────────
    ax2 = axes[1]
    all_parts = [t for _, t in fold_trades if not t.empty]

    if all_parts:
        all_trades = pd.concat(all_parts).sort_values("event_time")
        cum_all    = all_trades["net_pts"].cumsum().values
        peak_all   = np.maximum.accumulate(cum_all)

        ax2.plot(range(len(cum_all)), cum_all,
                 color="#2E86AB", linewidth=2, label="Equity (OOS agregado)")
        ax2.fill_between(
            range(len(cum_all)), cum_all, peak_all,
            alpha=0.25, color="#C1121F", label="Drawdown"
        )
    ax2.axhline(0, color="black", linewidth=0.8, linestyle="--")
    ax2.set_title("Equity Agregada (OOS) + Drawdown")
    ax2.set_xlabel("Trade #")
    ax2.set_ylabel("Cumulative PnL (pts)")
    ax2.legend(fontsize=9)
    ax2.grid(True, alpha=0.25)

    plt.suptitle(
        "NEUTRAL Alpha Strategy — Walk-Forward OOS Performance\n"
        f"WDO-EVOLVED-QUANT | Fase 2 | "
        f"stop={ATR_MULTIPLIER}×ATR · TP={TP_RATIO}:1 · hold={MAX_HOLD_BARS}bars",
        fontsize=10,
    )
    plt.tight_layout()
    plt.savefig(output_path, dpi=130)
    plt.close()
    print(f"  Equity curve salva: {output_path.name}")


# ══════════════════════════════════════════════════════════════════════════════
# 6. WALK-FORWARD (sklearn TimeSeriesSplit)
# ══════════════════════════════════════════════════════════════════════════════

def run_walk_forward(
    df            : pd.DataFrame,
    filtered_ev   : pd.DataFrame,
    atr_series    : pd.Series,
    n_folds       : int = 3,
) -> tuple[list[dict], list[tuple[int, pd.DataFrame]]]:
    """
    Executa walk-forward expanding window com sklearn.model_selection.TimeSeriesSplit.

    Para cada fold:
      TRAIN : apenas para contar eventos (sem fitting de parâmetros)
      TEST  : backtest real — métricas OOS

    Retorna (fold_results, fold_trades) para posterior análise.
    """
    try:
        from sklearn.model_selection import TimeSeriesSplit
    except ImportError:  # pragma: no cover
        # Fallback manual se sklearn não estiver instalado
        return _run_walk_forward_manual(df, filtered_ev, atr_series, n_folds)

    if filtered_ev.empty:
        return [], []

    # Ordenar por datetime para garantir sequência cronológica
    ev_sorted = filtered_ev.sort_values("event_time" if "event_time" in filtered_ev.columns
                                         else "datetime").reset_index(drop=True)
    n_events  = len(ev_sorted)

    if n_events < n_folds + 1:
        return [], []

    tscv         = TimeSeriesSplit(n_splits=n_folds)
    fold_results : list[dict] = []
    fold_trades  : list[tuple[int, pd.DataFrame]] = []

    for fold_idx, (train_idx, test_idx) in enumerate(tscv.split(range(n_events))):
        train_ev = ev_sorted.iloc[train_idx]
        test_ev  = ev_sorted.iloc[test_idx]

        train_n = len(train_ev)
        test_n  = len(test_ev)

        if test_n < 2:
            fold_results.append({
                "fold": fold_idx + 1, "train_n": train_n, "test_n": test_n,
                "win_rate": float("nan"), "expectancy_pts": float("nan"),
                "p_value": float("nan"),
            })
            fold_trades.append((fold_idx + 1, pd.DataFrame()))
            continue

        trades  = backtest_events(df, test_ev, atr_series)
        metrics = compute_metrics(trades)

        fold_trades.append((fold_idx + 1, trades))

        if metrics.get("insufficient"):
            fold_results.append({
                "fold": fold_idx + 1, "train_n": train_n, "test_n": test_n,
                "win_rate": float("nan"), "expectancy_pts": float("nan"),
                "p_value": float("nan"),
            })
        else:
            fold_results.append({
                "fold"           : fold_idx + 1,
                "train_n"        : train_n,
                "test_n"         : test_n,
                "win_rate"       : metrics["hit_rate"],
                "expectancy_pts" : metrics["expectancy"],
                "p_value"        : metrics["p_value"],
            })

    return fold_results, fold_trades


def _run_walk_forward_manual(
    df          : pd.DataFrame,
    filtered_ev : pd.DataFrame,
    atr_series  : pd.Series,
    n_folds     : int,
) -> tuple[list[dict], list[tuple[int, pd.DataFrame]]]:
    """Fallback expanding window sem sklearn."""
    ev_sorted = filtered_ev.sort_values("datetime").reset_index(drop=True)
    n_events  = len(ev_sorted)
    test_size = max(1, n_events // (n_folds + 1))

    fold_results : list[dict] = []
    fold_trades  : list[tuple[int, pd.DataFrame]] = []

    for k in range(1, n_folds + 1):
        train_end = k * test_size
        test_end  = (k + 1) * test_size if k < n_folds else n_events
        if train_end >= n_events:
            break

        train_ev = ev_sorted.iloc[:train_end]
        test_ev  = ev_sorted.iloc[train_end:test_end]
        trades   = backtest_events(df, test_ev, atr_series)
        metrics  = compute_metrics(trades)

        fold_trades.append((k, trades))
        if metrics.get("insufficient"):
            fold_results.append({
                "fold": k, "train_n": len(train_ev), "test_n": len(test_ev),
                "win_rate": float("nan"), "expectancy_pts": float("nan"),
                "p_value": float("nan"),
            })
        else:
            fold_results.append({
                "fold": k, "train_n": len(train_ev), "test_n": len(test_ev),
                "win_rate": metrics["hit_rate"], "expectancy_pts": metrics["expectancy"],
                "p_value": metrics["p_value"],
            })

    return fold_results, fold_trades


# ══════════════════════════════════════════════════════════════════════════════
# 7. ENTRY POINT PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

def run_strategy_validation(
    df         : pd.DataFrame,
    events     : pd.DataFrame,
    output_dir : Path,
    n_folds    : int = 3,
) -> dict:
    """
    Entry point chamado pelo pipeline principal (extreme_event_analysis_v2.py).

    Parâmetros
    ----------
    df         : DataFrame OOS (test split) com colunas OHLCV + M1 + M2.
    events     : DataFrame de eventos extraídos por extract_events().
    output_dir : Diretório para salvar plots e CSVs.
    n_folds    : número de folds para TimeSeriesSplit (default 3).

    Retorna dict com resultados agregados para uso posterior.
    """
    print(f"\n  {SEP}")
    print(f"  NEUTRAL ALPHA — STRATEGY VALIDATION v1.0")
    print(f"  {SEP}")

    # ── Guardrails de entrada ────────────────────────────────────────────────
    if events.empty:
        print("  Sem eventos — strategy validation ignorada.")
        print(f"  {SEP}\n")
        return {}

    if "event_direction" not in events.columns:
        print("  Coluna event_direction ausente — ignorada.")
        print(f"  {SEP}\n")
        return {}

    # ── ATR sobre o DataFrame OOS ────────────────────────────────────────────
    atr_series = _compute_atr(df)

    # ── Configuração da estratégia ────────────────────────────────────────────
    print(f"\n  Parametros da estratégia")
    print(f"  {SEP2}")
    print(f"  ATR stop      : {ATR_MULTIPLIER}× ATR({ATR_PERIOD})")
    print(f"  Take-profit   : {TP_RATIO}:1  (simétrico ao stop)")
    print(f"  Max hold      : {MAX_HOLD_BARS} barras de 1 min")
    print(f"  Custo RT      : {COST_RT:.2f} pts  (slippage + comissão + B3)")
    print(f"  Entry         : abertura da barra seguinte ao evento")

    # ── Seleção do filtro ────────────────────────────────────────────────────
    filtered_ev, tier_label = apply_neutral_filter(events)
    n_filtered = len(filtered_ev)

    n_neutral = (events["event_direction"] == "NEUTRAL").sum()
    print(f"\n  Filtro de eventos")
    print(f"  {SEP2}")
    print(f"  total NEUTRAL        : {n_neutral}")
    print(f"  após filtro ativo    : {n_filtered}")
    print(f"  tier                 : {tier_label}")

    if n_filtered < MIN_EVENTS_TOTAL:
        print(f"\n  Eventos insuficientes para backtest (n={n_filtered}, mínimo={MIN_EVENTS_TOTAL}).")
        print(f"  {SEP}\n")
        return {}

    # ── Backtest in-sample (todos os eventos filtrados) ───────────────────────
    print(f"\n  In-Sample Backtest  (referência — TODOS os {n_filtered} eventos filtrados)")
    print(f"  {SEP2}")
    all_trades = backtest_events(df, filtered_ev, atr_series)
    is_metrics = compute_metrics(all_trades)
    _print_metrics("In-Sample", is_metrics)

    # Salvar trades in-sample
    if not all_trades.empty:
        out_csv = output_dir / "neutral_strategy_trades_insample.csv"
        all_trades.to_csv(out_csv, index=False)
        print(f"  Trades salvos: {out_csv.name}")

    # ── Walk-Forward (OOS) ───────────────────────────────────────────────────
    print(f"\n  Walk-Forward OOS  (sklearn TimeSeriesSplit, {n_folds} folds, expanding)")
    print(f"  {SEP2}")
    print(f"  {'fold':>5}  {'train_n':>8}  {'test_n':>7}  "
          f"{'win_rate':>9}  {'exp_pts':>9}  {'p_val':>7}")
    print(f"  {SEP2}")

    fold_results, fold_trades = run_walk_forward(df, filtered_ev, atr_series, n_folds)

    for r in fold_results:
        wr_str  = f"{r['win_rate']:.1%}" if not pd.isna(r["win_rate"]) else "n/a"
        exp_str = f"{r['expectancy_pts']:+.4f}" if not pd.isna(r["expectancy_pts"]) else "n/a"
        pv_str  = f"{r['p_value']:.4f}"         if not pd.isna(r["p_value"])         else "n/a"
        print(f"  fold{r['fold']:>2}  {r['train_n']:>8}  {r['test_n']:>7}  "
              f"{wr_str:>9}  {exp_str:>9}  {pv_str:>7}")

    # ── Agregar resultados OOS ────────────────────────────────────────────────
    valid = [r for r in fold_results if not pd.isna(r["expectancy_pts"])]
    all_oos_trades = pd.concat(
        [t for _, t in fold_trades if not t.empty], ignore_index=True
    ) if fold_trades else pd.DataFrame()

    print(f"\n  {SEP2}")
    print(f"  AGGREGATE OOS")
    print(f"  {SEP2}")

    if valid:
        exps          = [r["expectancy_pts"] for r in valid]
        mean_exp      = float(np.mean(exps))
        std_exp       = float(np.std(exps, ddof=1)) if len(exps) > 1 else 0.0
        stability     = mean_exp / (std_exp + 1e-9)
        n_pos_folds   = sum(1 for e in exps if e > 0)
        threshold     = max(2, int(np.ceil(len(valid) * 0.67)))

        print(f"  folds válidos   : {len(valid)}/{n_folds}")
        print(f"  folds positivos : {n_pos_folds}/{len(valid)}  (threshold≥{threshold})")
        print(f"  mean exp (OOS)  : {mean_exp:+.4f} pts  ({mean_exp*POINT_VALUE:+.2f} R$)")
        print(f"  std  exp (OOS)  : {std_exp:.4f} pts")
        print(f"  stability score : {stability:.3f}  (mean/std — >=1.0 = estável)")

        if not all_oos_trades.empty:
            oos_metrics = compute_metrics(all_oos_trades)
            if not oos_metrics.get("insufficient"):
                print(f"  max drawdown    : {oos_metrics['max_dd_pts']:.2f} pts")
                print(f"  profit factor   : {oos_metrics['profit_factor']:.2f}")
                print(f"  hit rate OOS    : {oos_metrics['hit_rate']:.1%}")

        # Robustness flag
        robust = (
            n_pos_folds >= threshold
            and mean_exp > 0
            and stability >= 1.0
        )

        print(f"\n  {SEP2}")
        if robust:
            print(f"  ROBUSTNESS FLAG : [TRUE]  — alpha estável fora da amostra")
            print(f"    {n_pos_folds}/{len(valid)} folds positivos, "
                  f"stability={stability:.2f} >= 1.0, mean_exp > 0")
        else:
            print(f"  ROBUSTNESS FLAG : [FALSE] — alpha NÃO robusto fora da amostra")
            if n_pos_folds < threshold:
                print(f"    {n_pos_folds}/{len(valid)} folds positivos < {threshold} exigidos")
            if mean_exp <= 0:
                print(f"    mean_exp={mean_exp:+.4f} <= 0")
            if stability < 1.0:
                print(f"    stability={stability:.3f} < 1.0 — alta variância entre folds")
    else:
        print("  Nenhum fold válido para agregação.")
        robust    = False
        mean_exp  = float("nan")
        std_exp   = float("nan")
        stability = float("nan")

    # ── Equity curve ─────────────────────────────────────────────────────────
    if fold_trades:
        plot_path = output_dir / "neutral_strategy_equity_curve.png"
        plot_equity_curve(fold_trades, plot_path)

    # ── Salvar resultados OOS ─────────────────────────────────────────────────
    if not all_oos_trades.empty:
        out_oos = output_dir / "neutral_strategy_trades_oos.csv"
        all_oos_trades.to_csv(out_oos, index=False)
        print(f"  Trades OOS salvos: {out_oos.name}")

    print(f"  {SEP}\n")

    return {
        "tier_label"   : tier_label,
        "n_filtered"   : n_filtered,
        "n_folds"      : n_folds,
        "fold_results" : fold_results,
        "mean_exp"     : mean_exp,
        "std_exp"      : std_exp,
        "stability"    : stability,
        "robust"       : robust,
    }
