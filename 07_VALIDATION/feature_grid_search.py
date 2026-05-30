"""
feature_grid_search.py
WDO-EVOLVED-QUANT | Fase 2 — Feature Grid Search
Versão: 1.0 | 28/05/2026

Framework científico anti-overfitting para descoberta sistemática de edges
condicionais em eventos de volume extremo WDO.

ADVERTÊNCIA METODOLÓGICA
------------------------
Este módulo executa centenas de testes simultâneos sobre um único dataset.
Mesmo com correção FDR, o risco de data mining bias é ALTO com amostras
pequenas (<100 eventos totais). Resultados devem ser tratados como hipóteses
para validação futura com novos dados, não como edges confirmados.

Pipeline de análise
-------------------
1. Grid Search       — todas as combinações de regime × event_type × direction × horizon
2. FDR Correction    — Benjamini-Hochberg para controlar falsos positivos
3. Robustness Filter — n>=30, exp>0, PF>1.2, Sharpe>0.5, p_fdr<0.05
4. Walk-Forward      — 5 folds expanding window (sklearn TimeSeriesSplit)
5. Fold Consistency  — >=70% dos folds válidos com expectancy positiva
6. Final Ranking     — por robustez × estabilidade × expectancy OOS
7. Exports           — CSVs + 5 gráficos

Entry point
-----------
    from feature_grid_search import run_feature_research
    run_feature_research(path_df_full, output_dir)

Onde path_df_full é o resultado de compute_path_returns() sobre TODOS
os dados (treino + teste) para maximizar o tamanho da amostra.
"""

from __future__ import annotations

import itertools
import warnings
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from scipy.stats import binomtest

warnings.filterwarnings("ignore", category=RuntimeWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

# ── Parâmetros do framework (documentar, não otimizar) ────────────────────────
POINT_VALUE        = 10.0    # R$/ponto WDO

# Filtro de robustez — thresholds conservadores
MIN_N              = 30      # mínimo de trades por setup
MIN_EXP            = 0.0     # expectancy mínima (> 0 = positiva)
MIN_PF             = 1.2     # profit factor mínimo
MIN_SHARPE         = 0.5     # Sharpe simplificado mínimo
MAX_P_FDR          = 0.05    # p-value FDR-corrigido máximo

# Walk-forward
WF_FOLDS           = 5       # número de folds (TimeSeriesSplit)
WF_MIN_FOLD_N      = 5       # mínimo de trades por fold para ser válido
WF_CONSISTENCY_THR = 0.70    # fração mínima de folds positivos

# Plot
TOP_N_SETUPS       = 5       # top N setups para equity curves
FDR_ALPHA          = 0.05    # nível FDR

SEP  = "═" * 70
SEP2 = "─" * 70

# Dimensões do grid search
# Cada key mapeia para a coluna em path_df e os valores possíveis
GRID_DIMS: dict[str, list[str]] = {
    "vol_regime"    : ["LOW", "MID", "HIGH"],
    "trend_regime"  : ["TREND_UP", "RANGE", "TREND_DOWN"],
    "session_regime": ["OPENING", "CORE", "CLOSING"],
    "event_type"    : ["INITIATION", "ABSORPTION", "EXHAUSTION", "NONE"],
    "event_direction": ["BULLISH", "BEARISH", "NEUTRAL"],
}


# ══════════════════════════════════════════════════════════════════════════════
# 1. MÉTRICAS DE SUBSET
# ══════════════════════════════════════════════════════════════════════════════

def _metrics_for_subset(subset: pd.DataFrame) -> dict:
    """
    Calcula métricas completas para um subconjunto de path_df.

    Cada linha representa um trade (um (evento, horizonte) specific).
    O subset já deve estar filtrado para um único horizonte ou horizonte
    agregado — o chamador decide a granularidade.
    """
    n = len(subset)
    if n < 3:
        return {"n": n, "insufficient": True}

    pnl  = subset["net_pts"].values.astype(float)
    wins = subset["win"].values.astype(bool)

    hit_rate   = float(wins.mean())
    exp        = float(pnl.mean())
    pnl_std    = float(pnl.std(ddof=1)) if n > 1 else 0.0
    sharpe     = exp / (pnl_std + 1e-9)

    gain_sum = float(pnl[pnl > 0].sum()) if (pnl > 0).any() else 0.0
    loss_sum = float(abs(pnl[pnl < 0].sum())) if (pnl < 0).any() else 1e-9
    pf       = gain_sum / (loss_sum + 1e-9)

    cum_pnl  = np.cumsum(pnl)
    peak     = np.maximum.accumulate(cum_pnl)
    max_dd   = float((peak - cum_pnl).max())

    n_wins = int(wins.sum())
    p_binom = float(binomtest(n_wins, n, 0.5, alternative="greater").pvalue)

    return {
        "n"          : n,
        "hit_rate"   : hit_rate,
        "expectancy" : exp,
        "exp_brl"    : exp * POINT_VALUE,
        "sharpe"     : sharpe,
        "max_dd"     : max_dd,
        "pf"         : pf,
        "p_binom"    : p_binom,
        "cum_pnl"    : cum_pnl,
        "insufficient": False,
    }


# ══════════════════════════════════════════════════════════════════════════════
# 2. FDR CORRECTION (Benjamini-Hochberg)
# ══════════════════════════════════════════════════════════════════════════════

def _benjamini_hochberg(
    pvals: np.ndarray,
    alpha: float = FDR_ALPHA,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Correção FDR Benjamini-Hochberg (1995).

    Controla a False Discovery Rate ao nível `alpha`.
    Mais liberal que Bonferroni — indicado para exploração de features.

    Retorna (rejected: bool array, adjusted_pvals: float array).

    Referência: Benjamini, Y. & Hochberg, Y. (1995). JRSS-B, 57(1), 289–300.
    """
    n      = len(pvals)
    if n == 0:
        return np.array([], dtype=bool), np.array([])

    order  = np.argsort(pvals)
    sorted_p = pvals[order]
    ranks    = np.arange(1, n + 1)

    # Adjusted p-values (FWER-style step-up)
    adj = np.minimum(1.0, sorted_p * n / ranks)
    # Enforce monotonicity (step-down)
    for i in range(n - 2, -1, -1):
        adj[i] = min(adj[i], adj[i + 1])

    # Reject if adjusted p-value < alpha
    rejected_sorted = adj < alpha

    # Reorder back to original order
    rev_order        = np.argsort(order)
    rejected         = rejected_sorted[rev_order]
    adj_pvals        = adj[rev_order]

    return rejected, adj_pvals


def _bonferroni_threshold(n_tests: int, alpha: float = FDR_ALPHA) -> float:
    """Retorna o threshold Bonferroni (mais conservador que BH-FDR)."""
    return alpha / max(n_tests, 1)


# ══════════════════════════════════════════════════════════════════════════════
# 3. GRID SEARCH
# ══════════════════════════════════════════════════════════════════════════════

def run_grid_search(
    path_df : pd.DataFrame,
    horizons: list[int] | None = None,
) -> pd.DataFrame:
    """
    Itera sobre todas as combinações de GRID_DIMS × horizon e calcula métricas.

    Para cada combinação:
      - filtra path_df pelas condições
      - calcula métricas se n >= 3
      - registra resultado

    Ao final aplica correção FDR (Benjamini-Hochberg) sobre todos os p_binom.

    Retorna DataFrame com uma linha por (setup_id, horizon).
    """
    if path_df.empty:
        return pd.DataFrame()

    if horizons is None:
        horizons = sorted(path_df["horizon"].unique().tolist())

    # Verificar quais dimensões existem em path_df
    available_dims = {
        k: v for k, v in GRID_DIMS.items() if k in path_df.columns
    }

    if not available_dims:
        print("  AVISO: nenhuma dimensão de regime/event encontrada em path_df.")
        return pd.DataFrame()

    dim_names  = list(available_dims.keys())
    dim_values = [available_dims[d] for d in dim_names]

    records: list[dict] = []

    total_combos = (
        sum(1 for _ in itertools.product(*dim_values)) * len(horizons)
    )
    print(f"  Testando {total_combos:,} combinações "
          f"({len(list(itertools.product(*dim_values)))} setups × {len(horizons)} horizontes)...")

    for combo in itertools.product(*dim_values):
        conditions = dict(zip(dim_names, combo))

        # Filtrar path_df pelas condições do combo
        mask = pd.Series(True, index=path_df.index)
        for col, val in conditions.items():
            mask &= path_df[col] == val

        subset_full = path_df[mask]

        for h in horizons:
            subset = subset_full[subset_full["horizon"] == h]
            m      = _metrics_for_subset(subset)

            row = {**conditions, "horizon": h}
            if m.get("insufficient"):
                row.update({
                    "n": m["n"], "hit_rate": None, "expectancy": None,
                    "exp_brl": None, "sharpe": None, "max_dd": None,
                    "pf": None, "p_binom": None, "p_binom_fdr": None,
                    "fdr_significant": False, "setup_key": str(tuple(combo)) + f"|h={h}",
                })
            else:
                row.update({
                    "n"           : m["n"],
                    "hit_rate"    : round(m["hit_rate"], 4),
                    "expectancy"  : round(m["expectancy"], 4),
                    "exp_brl"     : round(m["exp_brl"], 2),
                    "sharpe"      : round(m["sharpe"], 4),
                    "max_dd"      : round(m["max_dd"], 4),
                    "pf"          : round(m["pf"], 4),
                    "p_binom"     : round(m["p_binom"], 6),
                    "p_binom_fdr" : None,        # preenchido após
                    "fdr_significant": False,    # preenchido após
                    "setup_key"   : str(tuple(combo)) + f"|h={h}",
                })
            records.append(row)

    if not records:
        return pd.DataFrame()

    results = pd.DataFrame(records)

    # ── FDR correction sobre todos os p_binom não-nulos ──────────────────────
    valid_mask  = results["p_binom"].notna()
    pvals_array = results.loc[valid_mask, "p_binom"].values.astype(float)

    n_tests = valid_mask.sum()
    bonferroni_thr = _bonferroni_threshold(n_tests)

    if n_tests > 0:
        rejected, adj_pvals = _benjamini_hochberg(pvals_array)
        results.loc[valid_mask, "p_binom_fdr"]    = np.round(adj_pvals, 6)
        results.loc[valid_mask, "fdr_significant"] = rejected

    print(f"  Total testado    : {len(results):,}  (p válidos: {n_tests:,})")
    print(f"  Bonferroni thr   : {bonferroni_thr:.6f}  (muito restritivo)")
    print(f"  FDR BH sig       : {rejected.sum() if n_tests > 0 else 0} setups  "
          f"(alpha={FDR_ALPHA})")

    return results


# ══════════════════════════════════════════════════════════════════════════════
# 4. FILTRO DE ROBUSTEZ
# ══════════════════════════════════════════════════════════════════════════════

def filter_robust_setups(results: pd.DataFrame) -> pd.DataFrame:
    """
    Aplica critérios múltiplos de robustez.

    Critérios (todos obrigatórios):
      n >= MIN_N           — amostra mínima estatisticamente válida
      expectancy > MIN_EXP — expectancy líquida positiva após custo
      pf > MIN_PF          — profit factor > 1.2 (margem sobre random)
      sharpe > MIN_SHARPE  — Sharpe simplificado > 0.5
      p_binom_fdr < MAX_P_FDR — significância pós-FDR

    Retorna DataFrame dos setups aprovados, ordenado por Sharpe descendente.
    """
    if results.empty:
        return pd.DataFrame()

    has_fdr = results["p_binom_fdr"].notna().any()

    mask = (
        results["n"].fillna(0) >= MIN_N
    ) & (
        results["expectancy"].fillna(-99) > MIN_EXP
    ) & (
        results["pf"].fillna(0) > MIN_PF
    ) & (
        results["sharpe"].fillna(-99) > MIN_SHARPE
    )
    if has_fdr:
        mask &= results["p_binom_fdr"].fillna(1.0) < MAX_P_FDR

    robust = results[mask].copy()
    if not robust.empty:
        robust = robust.sort_values("sharpe", ascending=False).reset_index(drop=True)

    return robust


# ══════════════════════════════════════════════════════════════════════════════
# 5. WALK-FORWARD POR SETUP
# ══════════════════════════════════════════════════════════════════════════════

def _walkforward_single_setup(
    path_df   : pd.DataFrame,
    conditions: dict,
    horizon   : int,
    n_folds   : int = WF_FOLDS,
) -> dict:
    """
    Walk-forward expanding window para um único setup.

    Usa event_time para ordenação cronológica.
    Retorna dict com fold_results, n_positive_folds, consistency, stability.
    """
    try:
        from sklearn.model_selection import TimeSeriesSplit
        use_sklearn = True
    except ImportError:
        use_sklearn = False

    # Filtrar subset
    mask = pd.Series(True, index=path_df.index)
    for col, val in conditions.items():
        if col in path_df.columns:
            mask &= path_df[col] == val
    mask &= path_df["horizon"] == horizon

    subset = path_df[mask].copy()
    if subset.empty or "event_time" not in subset.columns:
        return {"n_total": 0, "insufficient": True}

    subset = subset.sort_values("event_time").reset_index(drop=True)
    n_total = len(subset)

    if n_total < n_folds + 1:
        return {"n_total": n_total, "insufficient": True}

    fold_results: list[dict] = []

    if use_sklearn:
        tscv = TimeSeriesSplit(n_splits=n_folds)
        splits = list(tscv.split(range(n_total)))
    else:
        # Fallback manual
        test_size = max(1, n_total // (n_folds + 1))
        splits = [
            (list(range(0, (k + 1) * test_size)),
             list(range((k + 1) * test_size, min((k + 2) * test_size, n_total))))
            for k in range(n_folds)
            if (k + 1) * test_size < n_total
        ]

    for fold_idx, (train_idx, test_idx) in enumerate(splits):
        test_sub = subset.iloc[test_idx]
        m        = _metrics_for_subset(test_sub)

        if m.get("insufficient") or len(test_idx) < WF_MIN_FOLD_N:
            fold_results.append({
                "fold": fold_idx + 1,
                "train_n": len(train_idx),
                "test_n": len(test_idx),
                "expectancy": float("nan"),
                "win_rate": float("nan"),
                "p_value": float("nan"),
                "valid": False,
            })
        else:
            fold_results.append({
                "fold": fold_idx + 1,
                "train_n": len(train_idx),
                "test_n": len(test_idx),
                "expectancy": m["expectancy"],
                "win_rate": m["hit_rate"],
                "p_value": m["p_binom"],
                "valid": True,
            })

    valid_folds    = [f for f in fold_results if f["valid"]]
    n_valid        = len(valid_folds)
    n_positive     = sum(1 for f in valid_folds if f["expectancy"] > 0)
    consistency    = n_positive / n_valid if n_valid > 0 else 0.0
    exps           = [f["expectancy"] for f in valid_folds]
    stability      = (
        float(np.mean(exps)) / (float(np.std(exps, ddof=1)) + 1e-9)
        if len(exps) > 1 else float("nan")
    )

    return {
        "n_total"     : n_total,
        "n_folds"     : n_folds,
        "n_valid_folds": n_valid,
        "n_positive"  : n_positive,
        "consistency" : consistency,
        "stability"   : stability,
        "fold_results": fold_results,
        "insufficient": n_valid == 0,
    }


def walkforward_all_robust(
    path_df      : pd.DataFrame,
    robust_setups: pd.DataFrame,
    n_folds      : int = WF_FOLDS,
) -> pd.DataFrame:
    """
    Executa walk-forward para cada setup robusto.

    Adiciona colunas ao DataFrame de resultados:
      wf_n_valid_folds, wf_n_positive, wf_consistency, wf_stability,
      wf_passes (bool: consistency >= WF_CONSISTENCY_THR)
    """
    if robust_setups.empty or path_df.empty:
        return robust_setups

    dim_cols = [c for c in GRID_DIMS if c in robust_setups.columns]

    wf_records: list[dict] = []

    for _, row in robust_setups.iterrows():
        conditions = {c: row[c] for c in dim_cols if pd.notna(row.get(c))}
        horizon    = int(row["horizon"])

        wf = _walkforward_single_setup(path_df, conditions, horizon, n_folds)

        wf_records.append({
            "setup_key"       : row.get("setup_key", ""),
            "wf_n_valid"      : wf.get("n_valid_folds", 0),
            "wf_n_positive"   : wf.get("n_positive", 0),
            "wf_consistency"  : round(wf.get("consistency", 0.0), 3),
            "wf_stability"    : round(wf.get("stability", float("nan")), 3),
            "wf_passes"       : wf.get("consistency", 0.0) >= WF_CONSISTENCY_THR,
            "wf_insufficient" : wf.get("insufficient", True),
        })

    wf_df  = pd.DataFrame(wf_records)
    result = robust_setups.merge(wf_df, on="setup_key", how="left")
    return result


# ══════════════════════════════════════════════════════════════════════════════
# 6. VISUALIZAÇÕES
# ══════════════════════════════════════════════════════════════════════════════

def _pivot_for_heatmap(
    results : pd.DataFrame,
    col_x   : str,
    col_y   : str,
    value   : str,
    horizon : int,
    direction: str,
) -> np.ndarray | None:
    """
    Cria pivot table para heatmap de (col_x, col_y, value) filtrado.

    Retorna uma tupla (matrix_float64, row_labels, col_labels) ou None se
    não houver dados suficientes.

    Garante dtype float64 explícito para evitar TypeError no imshow()
    causado por colunas com dtype object (None Python vs np.nan).
    """
    if col_x not in results.columns or col_y not in results.columns:
        return None

    sub = results[
        (results["event_direction"] == direction) &
        (results["horizon"]         == horizon)
    ].copy()

    if sub.empty:
        return None

    # Converter coluna para float antes do pivot — elimina None/object
    sub[value] = pd.to_numeric(sub[value], errors="coerce")

    sub_valid = sub[sub[value].notna()]
    if sub_valid.empty:
        return None

    pivot = sub_valid.pivot_table(
        values=value, index=col_y, columns=col_x, aggfunc="mean"
    )

    if pivot.empty:
        return None

    # Forçar dtype float64 — pivot_table pode retornar object quando há NaN misturado
    matrix = pivot.to_numpy(dtype=float, na_value=np.nan)
    return matrix, list(pivot.index), list(pivot.columns)


def _draw_heatmap(
    ax        : plt.Axes,
    matrix    : np.ndarray,
    row_labels: list,
    col_labels: list,
    cmap      : str,
    vmin      : float,
    vmax      : float,
    fmt       : str = "+.3f",
    sig_thr   : float | None = None,
) -> None:
    """
    Desenha um heatmap no eixo `ax`.

    Recebe matrix já em float64, sem None.
    Se todos os valores forem NaN, escreve aviso no eixo e retorna.
    """
    finite = matrix[np.isfinite(matrix)]
    if finite.size == 0:
        ax.text(0.5, 0.5, "sem dados\n(n insuficiente)",
                ha="center", va="center", transform=ax.transAxes, fontsize=9,
                color="grey")
        return

    im = ax.imshow(matrix, cmap=cmap, vmin=vmin, vmax=vmax, aspect="auto")
    ax.set_xticks(range(len(col_labels)))
    ax.set_yticks(range(len(row_labels)))
    ax.set_xticklabels(col_labels, fontsize=9)
    ax.set_yticklabels(row_labels, fontsize=9)

    for i in range(len(row_labels)):
        for j in range(len(col_labels)):
            val = matrix[i, j]
            if np.isfinite(val):
                suffix = ("★" if sig_thr is not None and val < sig_thr else "")
                ax.text(j, i, f"{val:{fmt}}{suffix}",
                        ha="center", va="center", fontsize=8)

    plt.colorbar(im, ax=ax, shrink=0.8)


def plot_heatmaps(
    results    : pd.DataFrame,
    output_dir : Path,
    horizon    : int = 10,
) -> None:
    """
    Gera dois heatmaps para o horizonte selecionado:
      - vol_regime × trend_regime colorido por expectancy
      - vol_regime × trend_regime colorido por p_binom_fdr
    Por direção do evento (BULLISH / BEARISH / NEUTRAL).

    Todas as matrizes são convertidas explicitamente para float64 antes
    de qualquer chamada ao imshow() para evitar TypeError com dtype object.
    """
    if results.empty:
        return

    directions = ["BULLISH", "BEARISH", "NEUTRAL"]
    fig, axes  = plt.subplots(3, 2, figsize=(14, 14))

    for row_idx, direction in enumerate(directions):
        ax_exp = axes[row_idx, 0]
        ax_p   = axes[row_idx, 1]

        # ── Expectancy heatmap ────────────────────────────────────────────────
        pivot_exp = _pivot_for_heatmap(
            results, "vol_regime", "trend_regime", "expectancy", horizon, direction
        )
        if pivot_exp is not None:
            mat_exp, rows_exp, cols_exp = pivot_exp
            finite_exp = mat_exp[np.isfinite(mat_exp)]
            vmax = float(np.abs(finite_exp).max()) if finite_exp.size > 0 else 1.0
            vmax = max(vmax, 0.01)
            _draw_heatmap(ax_exp, mat_exp, rows_exp, cols_exp,
                          cmap="RdYlGn", vmin=-vmax, vmax=vmax, fmt="+.3f")
        else:
            ax_exp.text(0.5, 0.5, "sem dados\n(n insuficiente)",
                        ha="center", va="center", transform=ax_exp.transAxes,
                        fontsize=9, color="grey")
        ax_exp.set_title(f"{direction} — Expectancy (pts) | h={horizon}", fontsize=10)
        ax_exp.set_xlabel("vol_regime")
        ax_exp.set_ylabel("trend_regime")

        # ── P-value FDR heatmap ───────────────────────────────────────────────
        pivot_p = _pivot_for_heatmap(
            results, "vol_regime", "trend_regime", "p_binom_fdr", horizon, direction
        )
        if pivot_p is not None:
            mat_p, rows_p, cols_p = pivot_p
            _draw_heatmap(ax_p, mat_p, rows_p, cols_p,
                          cmap="RdYlGn_r", vmin=0.0, vmax=0.20,
                          fmt=".3f", sig_thr=FDR_ALPHA)
        else:
            ax_p.text(0.5, 0.5, "sem dados\n(n insuficiente)",
                      ha="center", va="center", transform=ax_p.transAxes,
                      fontsize=9, color="grey")
        ax_p.set_title(f"{direction} — p_binom FDR | h={horizon}", fontsize=10)
        ax_p.set_xlabel("vol_regime")
        ax_p.set_ylabel("trend_regime")

    plt.suptitle(
        f"Feature Grid Search — vol × trend | h={horizon}\n"
        f"WDO-EVOLVED-QUANT | ★ = FDR-significativo (alpha={FDR_ALPHA})",
        fontsize=11,
    )
    plt.tight_layout()
    out = output_dir / "grid_heatmap_expectancy.png"
    plt.savefig(out, dpi=130)
    plt.close()
    print(f"  Heatmap salvo: {out.name}")


def plot_scatter_pf_exp(
    results    : pd.DataFrame,
    output_dir : Path,
) -> None:
    """
    Scatter plot: profit factor vs expectancy.
    Ponto colorido por significância FDR.
    Tamanho proporcional a n.
    """
    if results.empty:
        return

    sub = results[results["expectancy"].notna() & results["pf"].notna()].copy()
    if sub.empty:
        return

    sub["sig_color"] = sub["fdr_significant"].map({True: "#2E86AB", False: "#BBBBBB"})
    sub["n_size"]    = (sub["n"].fillna(5) * 3).clip(10, 200)

    fig, ax = plt.subplots(figsize=(10, 7))
    for sig, label, color in [(True, "FDR-significativo", "#2E86AB"),
                               (False, "Não-significativo", "#BBBBBB")]:
        s = sub[sub["fdr_significant"] == sig]
        ax.scatter(
            s["expectancy"], s["pf"],
            s=s["n_size"], c=color, alpha=0.6, label=label, edgecolors="white", linewidth=0.5
        )

    ax.axvline(0, color="black", linewidth=0.8, linestyle="--")
    ax.axhline(MIN_PF, color="orange", linewidth=0.8, linestyle=":",
               label=f"PF threshold ({MIN_PF})")
    ax.set_xlabel("Expectancy líquida (pts)")
    ax.set_ylabel("Profit Factor")
    ax.set_title(
        "Feature Grid — Profit Factor vs Expectancy\n"
        f"Tamanho = n trades  |  Azul = FDR-significativo (alpha={FDR_ALPHA})",
        fontsize=10
    )
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.25)

    out = output_dir / "grid_scatter_pf_exp.png"
    plt.tight_layout()
    plt.savefig(out, dpi=130)
    plt.close()
    print(f"  Scatter PF×Exp salvo: {out.name}")


def plot_distribution_by_regime(
    results    : pd.DataFrame,
    output_dir : Path,
) -> None:
    """
    Distribuição de expectancy por vol_regime e trend_regime (boxplot).
    """
    if results.empty:
        return

    sub = results[results["expectancy"].notna()].copy()
    if sub.empty:
        return

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    for ax, col, vals in [
        (axes[0], "vol_regime",   ["LOW", "MID", "HIGH"]),
        (axes[1], "trend_regime", ["TREND_UP", "RANGE", "TREND_DOWN"]),
    ]:
        if col not in sub.columns:
            ax.axis("off")
            continue

        data = [sub[sub[col] == v]["expectancy"].dropna().values for v in vals]
        bp   = ax.boxplot(data, labels=vals, patch_artist=True,
                          medianprops=dict(color="black", linewidth=2))
        colors = ["#90C2E7", "#6BAE7F", "#E07B54"]
        for patch, color in zip(bp["boxes"], colors):
            patch.set_facecolor(color)
            patch.set_alpha(0.7)
        ax.axhline(0, color="red", linewidth=0.8, linestyle="--")
        ax.set_title(f"Distribuição de Expectancy por {col}")
        ax.set_ylabel("Expectancy (pts)")
        ax.grid(True, alpha=0.2, axis="y")

    plt.suptitle("Feature Grid — Distribuição por Regime | WDO-EVOLVED-QUANT", fontsize=11)
    plt.tight_layout()
    out = output_dir / "grid_distribution_regime.png"
    plt.savefig(out, dpi=130)
    plt.close()
    print(f"  Distribuição por regime salva: {out.name}")


def plot_equity_curves_top(
    path_df    : pd.DataFrame,
    top_setups : pd.DataFrame,
    output_dir : Path,
    top_n      : int = TOP_N_SETUPS,
) -> None:
    """
    Equity curves dos top N setups por Sharpe.
    Cada linha = cumulative PnL de um setup ao longo do tempo.
    """
    if top_setups.empty or path_df.empty:
        return

    dim_cols = [c for c in GRID_DIMS if c in top_setups.columns]
    top      = top_setups.head(top_n)

    fig, ax  = plt.subplots(figsize=(12, 6))
    palette  = plt.cm.tab10(np.linspace(0, 0.9, len(top)))

    for idx, (_, row) in enumerate(top.iterrows()):
        conditions = {c: row[c] for c in dim_cols if pd.notna(row.get(c))}
        horizon    = int(row["horizon"])

        mask = pd.Series(True, index=path_df.index)
        for col, val in conditions.items():
            if col in path_df.columns:
                mask &= path_df[col] == val
        mask &= path_df["horizon"] == horizon

        subset = path_df[mask].sort_values("event_time")
        if subset.empty:
            continue

        cum_pnl = subset["net_pts"].cumsum().values
        label   = (
            f"{row.get('event_direction','?')} | "
            f"vol={row.get('vol_regime','?')} | "
            f"tr={row.get('trend_regime','?')} | "
            f"h={horizon} | "
            f"n={int(row['n'])} | "
            f"Sh={row['sharpe']:.2f}"
        )
        ax.plot(range(len(cum_pnl)), cum_pnl, color=palette[idx],
                linewidth=2, label=label)

    ax.axhline(0, color="black", linewidth=0.8, linestyle="--")
    ax.set_title(
        f"Equity Curves — Top {min(top_n, len(top))} Setups (In-Sample)\n"
        "ADVERTÊNCIA: curvas IS — necessita validação com dados futuros",
        fontsize=10
    )
    ax.set_xlabel("Trade # (cronológico)")
    ax.set_ylabel("Cumulative PnL (pts)")
    ax.legend(fontsize=7, loc="upper left")
    ax.grid(True, alpha=0.25)

    plt.tight_layout()
    out = output_dir / "grid_equity_top_setups.png"
    plt.savefig(out, dpi=130)
    plt.close()
    print(f"  Equity curves top setups: {out.name}")


def plot_horizon_sensitivity(
    results    : pd.DataFrame,
    top_setups : pd.DataFrame,
    output_dir : Path,
) -> None:
    """
    Para cada setup robusto, plota expectancy vs horizonte.
    Permite identificar quais horizontes são mais estáveis.
    """
    if top_setups.empty or results.empty:
        return

    dim_cols  = [c for c in GRID_DIMS if c in top_setups.columns]
    top       = top_setups.head(TOP_N_SETUPS)
    horizons  = sorted(results["horizon"].unique())

    fig, ax   = plt.subplots(figsize=(10, 6))
    palette   = plt.cm.tab10(np.linspace(0, 0.9, len(top)))

    for idx, (_, row) in enumerate(top.iterrows()):
        cond_mask = pd.Series(True, index=results.index)
        for col in dim_cols:
            if pd.notna(row.get(col)):
                cond_mask &= results[col] == row[col]

        subset = results[cond_mask].sort_values("horizon")
        if subset.empty:
            continue

        label = (
            f"{row.get('event_direction','?')} | "
            f"vol={row.get('vol_regime','?')} | "
            f"tr={row.get('trend_regime','?')}"
        )
        ax.plot(
            subset["horizon"], subset["expectancy"],
            marker="o", color=palette[idx], linewidth=2, label=label
        )

    ax.axhline(0, color="black", linewidth=0.8, linestyle="--")
    ax.set_xlabel("Horizonte (barras)")
    ax.set_ylabel("Expectancy (pts)")
    ax.set_title("Sensibilidade ao Horizonte — Top Setups", fontsize=10)
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.25)

    plt.tight_layout()
    out = output_dir / "grid_horizon_sensitivity.png"
    plt.savefig(out, dpi=130)
    plt.close()
    print(f"  Sensibilidade ao horizonte: {out.name}")


# ══════════════════════════════════════════════════════════════════════════════
# 7. RELATÓRIO FINAL
# ══════════════════════════════════════════════════════════════════════════════

def print_final_report(
    all_results   : pd.DataFrame,
    robust_setups : pd.DataFrame,
    wf_results    : pd.DataFrame,
) -> None:
    """
    Imprime relatório estruturado com interpretação dos resultados.
    """
    print(f"\n  {SEP}")
    print(f"  FEATURE GRID SEARCH — RELATÓRIO FINAL")
    print(f"  {SEP}")

    n_total_setups = len(all_results)
    n_with_data    = all_results["n"].fillna(0).ge(MIN_N).sum()
    n_fdr_sig      = all_results["fdr_significant"].sum() if "fdr_significant" in all_results.columns else 0
    n_robust       = len(robust_setups)

    wf_passing     = (
        wf_results["wf_passes"].sum()
        if not wf_results.empty and "wf_passes" in wf_results.columns
        else 0
    )

    print(f"\n  FUNIL DE SELEÇÃO")
    print(f"  {SEP2}")
    print(f"  1. Total combinações testadas : {n_total_setups:>6,}")
    print(f"  2. Com n >= {MIN_N} trades      : {n_with_data:>6,}")
    print(f"  3. FDR-significativos (BH)    : {n_fdr_sig:>6,}")
    print(f"  4. Passam filtro robusto      : {n_robust:>6,}")
    print(f"     (exp>0, PF>{MIN_PF}, Sharpe>{MIN_SHARPE}, p_fdr<{MAX_P_FDR})")
    print(f"  5. Walk-forward consistentes  : {wf_passing:>6,}")
    print(f"     (>={WF_CONSISTENCY_THR:.0%} dos folds positivos)")

    # Diagnóstico por direção
    print(f"\n  DISTRIBUIÇÃO POR DIREÇÃO (setups com n>={MIN_N})")
    print(f"  {SEP2}")
    sub_n = all_results[all_results["n"].fillna(0) >= MIN_N]
    for d in ["BULLISH", "BEARISH", "NEUTRAL"]:
        if "event_direction" in sub_n.columns:
            nd  = (sub_n["event_direction"] == d).sum()
            pos = (
                sub_n[sub_n["event_direction"] == d]["expectancy"].fillna(-99) > 0
            ).sum()
            print(f"  {d:<10}: {nd:>3} setups  ({pos:>3} com exp>0)")

    # Top robust setups
    if not wf_results.empty and "wf_passes" in wf_results.columns:
        confirmed = wf_results[wf_results["wf_passes"] == True]
    else:
        confirmed = robust_setups

    if not confirmed.empty:
        print(f"\n  EDGES CONFIRMADOS (robusto + walk-forward)")
        print(f"  {SEP2}")
        dim_cols = [c for c in GRID_DIMS if c in confirmed.columns]
        cols_show = dim_cols + [
            "horizon", "n", "expectancy", "sharpe", "pf",
            "wf_consistency", "wf_stability"
        ]
        cols_show = [c for c in cols_show if c in confirmed.columns]
        top       = confirmed.head(10)
        print(top[cols_show].to_string(index=False, float_format=lambda x: f"{x:.3f}"))
    else:
        print(f"\n  EDGES CONFIRMADOS: nenhum sobreviveu ao filtro completo.")

    # Interpretação honesta
    print(f"\n  {SEP2}")
    print(f"  INTERPRETAÇÃO METODOLÓGICA")
    print(f"  {SEP2}")
    print(f"  ⚠  Grid search em dataset único → risco ALTO de data mining bias.")
    print(f"  ⚠  Resultados IS (in-sample) mesmo após FDR.")
    print(f"  ⚠  FDR-BH controla taxa de falsos positivos, NÃO elimina overfitting.")
    print(f"  ⚠  Walk-forward usa os mesmos dados — não é OOS verdadeiro.")

    if n_robust == 0:
        print(f"\n  CONCLUSÃO: Nenhum edge sobreviveu ao filtro de robustez.")
        print(f"  O alpha NEUTRAL original era provavelmente:")
        print(f"    • Small sample illusion (n={MIN_N} como mínimo)")
        print(f"    • Artefato estatístico pré-FDR")
        print(f"    • Overfitting ao período de teste disponível")
    elif wf_passing == 0:
        print(f"\n  CONCLUSÃO: {n_robust} setup(s) passaram o filtro IS mas")
        print(f"  nenhum foi consistente no walk-forward temporal.")
        print(f"  Sinal provável: IS-overfitting ou instabilidade temporal.")
    else:
        print(f"\n  CONCLUSÃO: {wf_passing} setup(s) sobreviveram ao pipeline completo.")
        print(f"  Estes são candidatos para validação com dados futuros (OOS real).")
        print(f"  PRÓXIMO PASSO: coletar 3+ meses adicionais e re-testar.")

    print(f"\n  {SEP}\n")


# ══════════════════════════════════════════════════════════════════════════════
# 8. ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def run_feature_research(
    path_df    : pd.DataFrame,
    output_dir : Path,
    horizons   : list[int] | None = None,
) -> dict:
    """
    Entry point do pipeline de pesquisa de features.

    Parâmetros
    ----------
    path_df    : resultado de compute_path_returns() sobre o dataset COMPLETO
                 (treino + teste) para maximizar tamanho da amostra.
    output_dir : diretório para salvar CSVs e gráficos.
    horizons   : lista de horizontes a testar (default: todos em path_df).

    Retorna dict com resultados agregados.
    """
    print(f"\n  {SEP}")
    print(f"  FEATURE GRID SEARCH — WDO-EVOLVED-QUANT v1.0")
    print(f"  {SEP}")

    if path_df.empty:
        print("  path_df vazio — feature research ignorada.")
        print(f"  {SEP}\n")
        return {}

    n_events = path_df["event_time"].nunique() if "event_time" in path_df.columns else "N/A"
    n_rows   = len(path_df)
    h_avail  = sorted(path_df["horizon"].unique().tolist()) if "horizon" in path_df.columns else []

    print(f"\n  Dataset")
    print(f"  {SEP2}")
    print(f"  eventos únicos  : {n_events}")
    print(f"  total linhas    : {n_rows:,}  ({n_rows} = n_eventos × n_horizontes)")
    print(f"  horizontes      : {h_avail}")
    print(f"\n  Critérios de robustez")
    print(f"  {SEP2}")
    print(f"  n mínimo        : {MIN_N}")
    print(f"  expectancy      : > {MIN_EXP}")
    print(f"  profit factor   : > {MIN_PF}")
    print(f"  Sharpe          : > {MIN_SHARPE}")
    print(f"  p FDR (BH)      : < {MAX_P_FDR}")
    print(f"  WF consistency  : >= {WF_CONSISTENCY_THR:.0%}  ({WF_FOLDS} folds)")
    print(f"\n  Avisos anti-overfitting")
    print(f"  {SEP2}")
    print(f"  Testando múltiplas combinações no mesmo dataset.")
    print(f"  FDR-BH corrige p-values mas NÃO substitui OOS verdadeiro.")
    print(f"  Resultados são HIPÓTESES, não edges confirmados.")

    # ── 1. Grid search ────────────────────────────────────────────────────────
    print(f"\n  [1/5] Grid Search")
    print(f"  {SEP2}")
    all_results = run_grid_search(path_df, horizons)

    if all_results.empty:
        print("  Nenhum resultado — dataset provavelmente muito pequeno.")
        print(f"  {SEP}\n")
        return {}

    # Salvar CSV completo
    out_grid = output_dir / "feature_grid_results.csv"
    all_results.drop(columns=["setup_key"], errors="ignore").to_csv(out_grid, index=False)
    print(f"  feature_grid_results.csv: {len(all_results):,} linhas")

    # ── 2. Filtro de robustez ─────────────────────────────────────────────────
    print(f"\n  [2/5] Filtro de Robustez")
    print(f"  {SEP2}")
    robust_setups = filter_robust_setups(all_results)
    print(f"  setups robustos : {len(robust_setups)}")

    if not robust_setups.empty:
        out_robust = output_dir / "robust_setups.csv"
        robust_setups.drop(columns=["setup_key"], errors="ignore").to_csv(
            out_robust, index=False
        )
        print(f"  robust_setups.csv salvo")

    # ── 3. Walk-forward ───────────────────────────────────────────────────────
    print(f"\n  [3/5] Walk-Forward ({WF_FOLDS} folds, TimeSeriesSplit)")
    print(f"  {SEP2}")
    if not robust_setups.empty:
        wf_results = walkforward_all_robust(path_df, robust_setups, WF_FOLDS)
        n_pass = int(wf_results["wf_passes"].sum()) if "wf_passes" in wf_results.columns else 0
        print(f"  setups com WF-consistency >= {WF_CONSISTENCY_THR:.0%}: {n_pass}")

        out_wf = output_dir / "walkforward_results.csv"
        wf_results.drop(columns=["setup_key"], errors="ignore").to_csv(
            out_wf, index=False
        )
        print(f"  walkforward_results.csv salvo")
    else:
        wf_results = pd.DataFrame()
        print("  Sem setups robustos para walk-forward.")

    # ── 4. Visualizações ──────────────────────────────────────────────────────
    print(f"\n  [4/5] Gerando visualizações")
    print(f"  {SEP2}")
    ref_horizon = 10 if 10 in h_avail else (h_avail[0] if h_avail else 10)
    plot_heatmaps(all_results, output_dir, horizon=ref_horizon)
    plot_scatter_pf_exp(all_results, output_dir)
    plot_distribution_by_regime(all_results, output_dir)

    top_for_curves = (
        wf_results[wf_results.get("wf_passes", pd.Series(False))]
        if not wf_results.empty and "wf_passes" in wf_results.columns
        else robust_setups
    )
    if top_for_curves.empty:
        top_for_curves = (
            all_results[all_results["n"].fillna(0) >= MIN_N]
            .sort_values("sharpe", ascending=False)
            .head(TOP_N_SETUPS)
        )

    if not top_for_curves.empty:
        plot_equity_curves_top(path_df, top_for_curves, output_dir)
        plot_horizon_sensitivity(all_results, top_for_curves, output_dir)

    # ── 5. Relatório ─────────────────────────────────────────────────────────
    print(f"\n  [5/5] Relatório")
    print_final_report(all_results, robust_setups, wf_results)

    return {
        "n_total_setups" : len(all_results),
        "n_robust"       : len(robust_setups),
        "n_wf_passing"   : (
            int(wf_results["wf_passes"].sum())
            if not wf_results.empty and "wf_passes" in wf_results.columns
            else 0
        ),
        "robust_setups"  : robust_setups,
        "all_results"    : all_results,
    }
