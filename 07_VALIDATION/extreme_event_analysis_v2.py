"""
extreme_event_analysis_v2.py
WDO-EVOLVED-QUANT | Fase 2 — Microestrutura
Versão: 2.4 | Data: 28/05/2026

Correções BUG-01 a BUG-07 + camadas M1 e M2:

  BUG-01: Direção do evento classificada (BULLISH / BEARISH / NEUTRAL)
  BUG-02: Teste binomial para win rate + Wilcoxon + permutation test
  BUG-03: Expectancy líquida com slippage regime-aware
  BUG-04: volume_ma com shift(1) — janela backward-looking pura
  BUG-05: Clustering filter — mínimo 21 barras entre eventos independentes
  BUG-06: Path analysis — horizontes [3, 5, 7, 10, 15, 20] barras
  BUG-07: Sensitivity analysis — thresholds [5, 7, 10, 12, 15]x

  M1 (v2.1): classify_event() → event_type (INITIATION/ABSORPTION/EXHAUSTION/NONE)
  M2 (v2.2): classify_regime() → vol_regime / trend_regime / session_regime
             Aplicado em load_and_prepare() após M1. Propaga por extract_events()
             e compute_path_returns() sem modificar nenhuma lógica estatística.
             Permite segmentação posterior: event_type × regime × horizon.

  v2.3     : strategy_neutral_alpha.py integrado como passo [7/10].
             Substitui walk-forward ad hoc por sklearn TimeSeriesSplit +
             backtest bar-a-bar com ATR stop, take-profit e sizing 1R.

  v2.4     : feature_grid_search.py integrado como passo [10/10].
             Grid search completo sobre vol × trend × session × event_type
             × direction × horizon, com correção FDR Benjamini-Hochberg,
             filtro de robustez multi-critério, walk-forward 5 folds e
             5 visualizações (heatmaps, scatter, equity, sensibilidade).
"""

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.stats import binomtest, wilcoxon

from event_classifier        import classify_event          # M1 — classificação tipológica de evento
from regime_classifier       import classify_regime         # M2 — vol / trend / session regime
from strategy_neutral_alpha  import run_strategy_validation # NEUTRAL strategy layer
from feature_grid_search     import run_feature_research    # Feature Grid Search

warnings.filterwarnings("ignore", category=RuntimeWarning)

sys.path.insert(0, str(Path(__file__).parent.parent))
from oos_engine import split_out_of_sample
from cost_model import COMMISSION_PER_CONTRACT, FEES_B3_PER_CONTRACT

# ── Caminhos ──────────────────────────────────────────────────────────────────
DATA_PATH  = Path(__file__).parent.parent / "data" / "raw" / "WDOFUT_processado.parquet"
OUTPUT_DIR = Path(__file__).parent.parent / "graficos"
OUTPUT_DIR.mkdir(exist_ok=True)

# ── Parâmetros (não otimizar — apenas documentar e medir) ────────────────────
VOL_LOOKBACK        = 50     # janela da média de volume histórico (barras)
DEFAULT_THRESHOLD   = 10.0   # threshold padrão para análise principal
MIN_EVENT_GAP       = 21     # BUG-05: mínimo de barras entre eventos independentes
POINT_VALUE         = 10.0   # R$/ponto (WDO)

# BUG-01: limiar de corpo/range para classificação de direção
BODY_RATIO_STRONG   = 0.30   # >= +30% → BULLISH; <= -30% → BEARISH; else NEUTRAL

# BUG-03: custo variável por regime de liquidez
SLIPPAGE_NORMAL     = 0.5    # slippage em condições normais (pts, por lado)
SLIPPAGE_EXTREME    = 1.0    # spread alargado durante volume extremo (pts, por lado)
COST_RT_NORMAL      = (2 * SLIPPAGE_NORMAL)  + COMMISSION_PER_CONTRACT + FEES_B3_PER_CONTRACT
COST_RT_EXTREME     = (2 * SLIPPAGE_EXTREME) + COMMISSION_PER_CONTRACT + FEES_B3_PER_CONTRACT

# BUG-06: horizontes de holding para path analysis
HORIZONS   = [3, 5, 7, 10, 15, 20]

# BUG-07: thresholds para sensitivity analysis
THRESHOLDS = [5.0, 7.0, 10.0, 12.0, 15.0]

# Resultado original (v1.0) — usado no relatório comparativo
_V1_RESULTS = {
    "n_events"         : 42,
    "direction_split"  : False,
    "clustering_filter": False,
    "cost_subtracted"  : False,
    "win_rate"         : 0.714,
    "expectancy_pct"   : 0.049,
    "ic_bootstrap_95"  : (-0.01, 0.10),
    "test_applied"     : "Bootstrap de retorno médio (IC contém zero → descartado como ruído)",
    "conclusao"        : "RUÍDO — prematura, teste inadequado para bias direcional",
}


# ═══════════════════════════════════════════════════════════════════════════════
# 1. CARGA E PREPARAÇÃO
#    Ponto de integração M1: classify_event() chamado no final desta função.
#    O DataFrame retornado já contém a coluna event_type em todas as barras.
# ═══════════════════════════════════════════════════════════════════════════════

def load_and_prepare(path: Path) -> pd.DataFrame:
    """
    Carrega o parquet, normaliza colunas e computa features de microestrutura.
    BUG-04: volume_ma usa shift(1) antes do rolling — exclui a barra atual.
    M1    : classify_event() adicionado ao final — popula coluna event_type.
    """
    df = pd.read_parquet(path)
    df["datetime"] = pd.to_datetime(df["datetime"])
    df = df.sort_values("datetime").reset_index(drop=True)

    # Normalizar nomes de coluna (fonte pode vir com ou sem acento)
    rename = {
        "maxima"    : "máxima",
        "minima"    : "mínima",
        "abertura"  : "abertura",
        "fechamento": "fechamento",
    }
    df.rename(columns={k: v for k, v in rename.items() if k in df.columns}, inplace=True)

    # BUG-04: shift(1) exclui a barra atual do denominador
    df["volume_ma"]  = (
        df["volume"]
        .shift(1)
        .rolling(VOL_LOOKBACK, min_periods=VOL_LOOKBACK)
        .mean()
    )
    df["volume_rel"] = df["volume"] / df["volume_ma"]

    # Morfologia da vela (usada por classify_direction e por classify_event)
    df["candle_range"] = df["máxima"]    - df["mínima"]
    df["candle_body"]  = df["fechamento"] - df["abertura"]
    df["body_ratio"]   = df["candle_body"] / (df["candle_range"] + 1e-9)

    # Buying pressure proxy: (close - low) / range → [0, 1]
    df["buying_pressure"] = (df["fechamento"] - df["mínima"]) / (df["candle_range"] + 1e-9)

    # ── M1: classificação tipológica (INITIATION / ABSORPTION / EXHAUSTION / NONE)
    df = classify_event(df)

    # ── M2: regime de mercado (vol_regime / trend_regime / session_regime)
    df = classify_regime(df)

    return df


# ═══════════════════════════════════════════════════════════════════════════════
# 2. BUG-01 — CLASSIFICAÇÃO DE DIREÇÃO (separada do event_type do M1)
# ═══════════════════════════════════════════════════════════════════════════════

def classify_direction(body_ratio: float) -> str:
    """
    Classifica a vela do evento em BULLISH / BEARISH / NEUTRAL.
    Ortogonal ao event_type do M1 — ambas as dimensões são mantidas.

    BULLISH : corpo positivo >= BODY_RATIO_STRONG do range
    BEARISH : corpo negativo <= -BODY_RATIO_STRONG do range
    NEUTRAL : corpo pequeno (absorption / doji)
    """
    if body_ratio >= BODY_RATIO_STRONG:
        return "BULLISH"
    if body_ratio <= -BODY_RATIO_STRONG:
        return "BEARISH"
    return "NEUTRAL"


# ═══════════════════════════════════════════════════════════════════════════════
# 3. BUG-05 — EXTRAÇÃO COM CLUSTERING FILTER
#    event_type é propagado automaticamente do df (já calculado em M1).
# ═══════════════════════════════════════════════════════════════════════════════

def extract_events(df: pd.DataFrame, threshold: float) -> pd.DataFrame:
    """
    Extrai eventos onde volume_rel > threshold respeitando independência.

    df deve ter índice inteiro sequencial (reset_index já aplicado).
    Eventos com distância < MIN_EVENT_GAP barras são descartados.

    Colunas de saída incluem:
      event_direction : BULLISH / BEARISH / NEUTRAL  (BUG-01)
      event_type      : INITIATION / ABSORPTION / EXHAUSTION / NONE  (M1)
      integer_pos     : posição inteira no df
    """
    candidate_positions = df.index[df["volume_rel"] > threshold].tolist()
    if not candidate_positions:
        return pd.DataFrame()

    # Clustering filter: garante independência entre eventos
    kept: list[int] = [candidate_positions[0]]
    for pos in candidate_positions[1:]:
        if pos - kept[-1] >= MIN_EVENT_GAP:
            kept.append(pos)

    events = df.loc[kept].copy()
    events["event_direction"] = events["body_ratio"].apply(classify_direction)
    events["integer_pos"]     = kept
    # event_type já está em events — herdado do df via M1 em load_and_prepare()
    return events.reset_index(drop=True)


# ═══════════════════════════════════════════════════════════════════════════════
# 4. BUG-03 + BUG-06 — PATH ANALYSIS COM CUSTO REGIME-AWARE
#    event_type propagado para os records, permitindo análise cruzada.
# ═══════════════════════════════════════════════════════════════════════════════

def compute_path_returns(
    df      : pd.DataFrame,
    events  : pd.DataFrame,
    horizons: list[int],
) -> pd.DataFrame:
    """
    Para cada (evento, horizonte h), calcula o retorno DIRECIONAL LÍQUIDO.

    event_type (M1) é propagado para cada record, permitindo cruzar
    event_direction × event_type sem alterar o pipeline estatístico.
    """
    records = []
    for _, ev in events.iterrows():
        pos            = int(ev["integer_pos"])
        base_px        = df.iloc[pos]["fechamento"]
        direction      = ev["event_direction"]
        event_type     = ev.get("event_type",     "NONE")     # M1
        vol_regime     = ev.get("vol_regime",     "UNKNOWN")  # M2
        trend_regime   = ev.get("trend_regime",   "UNKNOWN")  # M2
        session_regime = ev.get("session_regime", "UNKNOWN")  # M2
        ev_time        = ev["datetime"]
        vol_rel        = ev["volume_rel"]

        for h in horizons:
            if pos + h >= len(df):
                continue

            future_px = df.iloc[pos + h]["fechamento"]
            raw_pts   = future_px - base_px

            # Alinhar com a direção esperada do evento
            if direction == "BULLISH":
                directional_pts = raw_pts
            elif direction == "BEARISH":
                directional_pts = -raw_pts
            else:
                directional_pts = abs(raw_pts)

            net_pts = directional_pts - COST_RT_EXTREME

            records.append({
                "event_time"       : ev_time,
                "event_direction"  : direction,
                "event_type"       : event_type,     # M1
                "vol_regime"       : vol_regime,     # M2
                "trend_regime"     : trend_regime,   # M2
                "session_regime"   : session_regime, # M2
                "volume_rel"       : vol_rel,
                "horizon"          : h,
                "raw_pts"          : raw_pts,
                "directional_pts"  : directional_pts,
                "net_pts"          : net_pts,
                "win"              : net_pts > 0,
            })

    return pd.DataFrame(records)


# ═══════════════════════════════════════════════════════════════════════════════
# 5. BUG-02 — TESTES ESTATÍSTICOS CORRETOS
# ═══════════════════════════════════════════════════════════════════════════════

def run_statistical_tests(
    path_df  : pd.DataFrame,
    direction: str,
    horizon  : int,
) -> dict:
    """
    Para um (direction, horizon) específico executa 3 testes corretos:
      1. Binomial: win rate significativamente > 50%?
      2. Wilcoxon signed-rank: magnitude dos retornos líquidos > 0?
      3. Permutation test direcional
    """
    subset = path_df[
        (path_df["event_direction"] == direction) &
        (path_df["horizon"]         == horizon)
    ]

    n = len(subset)
    if n < 5:
        return {"n": n, "insufficient": True}

    net    = subset["net_pts"].values
    n_wins = int(subset["win"].sum())

    # 1. Teste binomial (unilateral: WR > 50%)
    binom_p = binomtest(n_wins, n, p=0.5, alternative="greater").pvalue

    # 2. Wilcoxon signed-rank (magnitude > 0)
    try:
        if np.sum(net != 0) >= 5 and not np.all(net >= 0) and not np.all(net <= 0):
            _, w_p = wilcoxon(net, alternative="greater")
        else:
            w_p = 1.0
    except Exception:
        w_p = 1.0

    # 3. Permutation test direcional (10 000 iterações)
    observed_mean = float(np.mean(net))
    rng = np.random.default_rng(seed=42)
    abs_net = np.abs(net)
    perm_means = np.array([
        float(np.mean(abs_net * rng.choice([-1.0, 1.0], size=n)))
        for _ in range(10_000)
    ])
    perm_p = float(np.mean(perm_means >= observed_mean))

    return {
        "n"                   : n,
        "n_wins"              : n_wins,
        "win_rate"            : n_wins / n,
        "expectancy_pts"      : observed_mean,
        "expectancy_brl"      : observed_mean * POINT_VALUE,
        "binom_p"             : float(binom_p),
        "wilcoxon_p"          : float(w_p),
        "perm_p"              : perm_p,
        "significant_binom"   : binom_p < 0.05,
        "significant_wilcoxon": w_p  < 0.05,
        "significant_perm"    : perm_p < 0.05,
        "insufficient"        : False,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 6. BUG-07 — SENSITIVITY ANALYSIS DE THRESHOLD
# ═══════════════════════════════════════════════════════════════════════════════

def sensitivity_analysis(df: pd.DataFrame, thresholds: list[float]) -> pd.DataFrame:
    """
    Para cada threshold e direção, calcula n_events, win_rate e expectancy
    líquida usando horizonte fixo de 10 barras.
    """
    records = []
    for thresh in thresholds:
        events = extract_events(df, thresh)
        if events.empty:
            for direction in ("BULLISH", "BEARISH", "NEUTRAL"):
                records.append({
                    "threshold": thresh, "direction": direction,
                    "n_events": 0, "win_rate": None, "expectancy_pts": None,
                })
            continue

        path = compute_path_returns(df, events, horizons=[10])
        if path.empty:
            continue

        for direction in ("BULLISH", "BEARISH", "NEUTRAL"):
            sub = path[path["event_direction"] == direction]
            if sub.empty:
                records.append({
                    "threshold": thresh, "direction": direction,
                    "n_events": 0, "win_rate": None, "expectancy_pts": None,
                })
                continue
            records.append({
                "threshold"     : thresh,
                "direction"     : direction,
                "n_events"      : len(sub),
                "win_rate"      : round(float(sub["win"].mean()), 4),
                "expectancy_pts": round(float(sub["net_pts"].mean()), 4),
            })

    return pd.DataFrame(records)


# ═══════════════════════════════════════════════════════════════════════════════
# 7. GRÁFICOS
# ═══════════════════════════════════════════════════════════════════════════════

def plot_path_by_direction(path_df: pd.DataFrame, output_path: Path) -> None:
    directions = ["BULLISH", "BEARISH", "NEUTRAL"]
    palette    = {"BULLISH": "#2E86AB", "BEARISH": "#C1121F", "NEUTRAL": "#6B6B6B"}

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))

    for ax, direction in zip(axes, directions):
        sub   = path_df[path_df["event_direction"] == direction]
        color = palette[direction]

        if sub.empty or sub["horizon"].nunique() < 2:
            ax.set_title(f"{direction}\n(sem dados suficientes)")
            ax.axis("off")
            continue

        hor_exp  = sub.groupby("horizon")["net_pts"].mean()
        hor_std  = sub.groupby("horizon")["net_pts"].std()
        hor_wr   = sub.groupby("horizon")["win"].mean()
        n_events = sub["event_direction"].count() // len(sub["horizon"].unique())

        ax.fill_between(
            hor_exp.index,
            hor_exp.values - hor_std.values * 0.5,
            hor_exp.values + hor_std.values * 0.5,
            alpha=0.12, color=color,
        )
        ax.plot(hor_exp.index, hor_exp.values, marker="o", color=color,
                linewidth=2, label="Exp. líquida (pts)")
        ax.axhline(0, color="black", linewidth=0.7, linestyle="--")
        ax.set_title(f"{direction}  (n={n_events} eventos)")
        ax.set_xlabel("Horizonte (barras de 1min)")
        ax.set_ylabel("Expectancy líquida (pontos)")
        ax.grid(True, alpha=0.25)

        ax2 = ax.twinx()
        ax2.plot(hor_wr.index, hor_wr.values, marker="s", color=color,
                 linewidth=1.2, linestyle=":", alpha=0.65)
        ax2.axhline(0.5, color="grey", linewidth=0.5, linestyle=":")
        ax2.set_ylim(0, 1)
        ax2.set_ylabel("Win rate", color="grey")

    plt.suptitle(
        "Path Analysis por Direção — Expectancy Líquida × Horizonte\n"
        f"(v2.1 · threshold={DEFAULT_THRESHOLD}x · gap≥{MIN_EVENT_GAP} · "
        f"custo RT={COST_RT_EXTREME:.2f}pts)",
        fontsize=11,
    )
    plt.tight_layout()
    plt.savefig(output_path, dpi=130)
    plt.close()
    print(f"   Gráfico salvo: {output_path.name}")


def plot_event_type_distribution(events: pd.DataFrame, output_path: Path) -> None:
    """Distribuição de event_type (M1) × event_direction por evento."""
    if events.empty or "event_type" not in events.columns:
        return

    palette = {"BULLISH": "#2E86AB", "BEARISH": "#C1121F", "NEUTRAL": "#6B6B6B"}
    types   = ["INITIATION", "ABSORPTION", "EXHAUSTION", "NONE"]
    directions = list(palette.keys())

    x = np.arange(len(types))
    width = 0.25
    fig, ax = plt.subplots(figsize=(11, 5))

    for i, (direction, color) in enumerate(palette.items()):
        counts = [
            len(events[(events["event_type"] == t) & (events["event_direction"] == direction)])
            for t in types
        ]
        ax.bar(x + i * width, counts, width, label=direction, color=color, alpha=0.82)

    ax.set_xticks(x + width)
    ax.set_xticklabels(types)
    ax.set_xlabel("Tipo de evento (M1)")
    ax.set_ylabel("Número de eventos")
    ax.set_title(
        f"Distribuição event_type × event_direction\n"
        f"(threshold={DEFAULT_THRESHOLD}x · n={len(events)} eventos independentes)"
    )
    ax.legend()
    ax.grid(True, alpha=0.25, axis="y")
    plt.tight_layout()
    plt.savefig(output_path, dpi=130)
    plt.close()
    print(f"   Gráfico salvo: {output_path.name}")


def plot_sensitivity(sens_df: pd.DataFrame, output_path: Path) -> None:
    if sens_df.empty:
        return

    palette = {"BULLISH": "#2E86AB", "BEARISH": "#C1121F", "NEUTRAL": "#6B6B6B"}
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), sharex=True)

    for direction, color in palette.items():
        sub = sens_df[(sens_df["direction"] == direction) & (sens_df["n_events"] > 0)]
        if sub.empty:
            continue
        ax1.plot(sub["threshold"], sub["win_rate"],
                 marker="o", color=color, label=direction, linewidth=1.8)
        ax2.plot(sub["threshold"], sub["expectancy_pts"],
                 marker="s", color=color, label=direction, linewidth=1.8)

    ax1.axhline(0.5, color="black", linestyle="--", linewidth=0.8)
    ax1.set_ylabel("Win rate (líquido)")
    ax1.set_title("Sensitivity analysis — Win rate por threshold × direção (h=10 barras)")
    ax1.legend()
    ax1.grid(True, alpha=0.25)

    ax2.axhline(0.0, color="black", linestyle="--", linewidth=0.8)
    ax2.set_xlabel("Threshold (× média de volume)")
    ax2.set_ylabel("Expectancy líquida (pontos)")
    ax2.set_title("Expectancy líquida por threshold × direção")
    ax2.legend()
    ax2.grid(True, alpha=0.25)

    plt.tight_layout()
    plt.savefig(output_path, dpi=130)
    plt.close()
    print(f"   Gráfico salvo: {output_path.name}")


# ═══════════════════════════════════════════════════════════════════════════════
# 8. RELATÓRIO COMPARATIVO
# ═══════════════════════════════════════════════════════════════════════════════

def print_comparison_report(
    new_events_total : int,
    new_events_by_dir: dict,
    stat_results     : dict,
    sens_df          : pd.DataFrame,
    events           : pd.DataFrame,
) -> None:
    SEP  = "=" * 72
    SEP2 = "─" * 72
    v1   = _V1_RESULTS

    print(f"\n{SEP}")
    print("  RELATÓRIO COMPARATIVO — v1.0 (original) vs v2.1 (corrigido + M1)")
    print(SEP)

    # Bloco 1: comparação estrutural
    print(f"\n{'':2}{'Item':<32} {'v1.0':<26} {'v2.1'}")
    print(f"{'':2}{SEP2}")
    rows = [
        ("Direção do evento",
            "NÃO (todos misturados)", "SIM (BULLISH/BEARISH/NEUTRAL)"),
        ("Classificação M1 (event_type)",
            "NÃO", "SIM (INITIATION/ABSORPTION/EXHAUSTION)"),
        ("Clustering filter",
            "NÃO", f"SIM (gap ≥ {MIN_EVENT_GAP} barras)"),
        ("Custo subtraído",
            "NÃO (bruto)", f"SIM ({COST_RT_EXTREME:.2f}pts RT extremo)"),
        ("Correção volume_ma",
            "NÃO (inclui barra atual)", "SIM (shift(1))"),
        ("Teste de win rate",
            "Bootstrap de magnitude", "Binomial + Wilcoxon + Permutation"),
        ("Horizontes testados",
            "Apenas h=20", str(HORIZONS)),
        ("Thresholds testados",
            "Apenas 10x", str(THRESHOLDS)),
        ("n eventos OOS",
            str(v1["n_events"]), str(new_events_total)),
        ("Win rate (total misturado)",
            f"{v1['win_rate']:.1%}", "Ver por direção abaixo"),
    ]
    for item, old_val, new_val in rows:
        print(f"{'':2}{item:<32} {old_val:<26} {new_val}")

    # Bloco 2: distribuição por direção
    print(f"\n{SEP2}")
    print("  DISTRIBUIÇÃO DE EVENTOS (event_direction × event_type):\n")
    if not events.empty and "event_type" in events.columns:
        cross = pd.crosstab(
            events["event_direction"], events["event_type"],
            margins=True, margins_name="TOTAL"
        )
        print(cross.to_string())
    else:
        print("  (sem eventos)")

    # Bloco 3: matriz de resultados
    print(f"\n{SEP2}")
    print("  MATRIZ — EXPECTANCY LÍQUIDA (pts) | WIN RATE | ★ = p<0.05\n")
    horizons_str = "".join(f"  h={h:<3}" for h in HORIZONS)
    print(f"{'':4}{'Direção':<10}{horizons_str}")

    for direction in ("BULLISH", "BEARISH", "NEUTRAL"):
        row_exp = f"{'':4}{direction:<10}"
        row_wr  = f"{'':4}{'WR':.<10}"
        row_sig = f"{'':4}{'sig':.<10}"
        for h in HORIZONS:
            stats = stat_results.get((direction, h), {})
            if stats.get("insufficient"):
                row_exp += f"  {'n/a':<5}"
                row_wr  += f"  {'n/a':<5}"
                row_sig += f"  {'—':<5}"
            else:
                row_exp += f"  {stats['expectancy_pts']:+.2f} "
                row_wr  += f"  {stats['win_rate']:.0%}   "
                marker   = "★" if (stats["significant_binom"] or
                                    stats["significant_wilcoxon"] or
                                    stats["significant_perm"]) else " "
                row_sig += f"  {marker:<5}"
        print(row_exp)
        print(row_wr)
        print(row_sig)
        print()

    # Bloco 4: detalhamento dos significativos
    print(f"{SEP2}")
    print("  COMBINAÇÕES COM p < 0.05:\n")
    found = False
    for (direction, horizon), stats in sorted(stat_results.items()):
        if stats.get("insufficient"):
            continue
        if stats["significant_binom"] or stats["significant_wilcoxon"] or stats["significant_perm"]:
            found = True
            print(f"  [{direction} | h={horizon:2d}]")
            print(f"    n          : {stats['n']}")
            print(f"    Win rate   : {stats['win_rate']:.1%}  ({stats['n_wins']}/{stats['n']})")
            print(f"    Exp líq.   : {stats['expectancy_pts']:+.4f} pts  "
                  f"(R$ {stats['expectancy_brl']:+.2f})")
            print(f"    Binomial p : {stats['binom_p']:.4f}"
                  f"  {'✓' if stats['significant_binom']    else '—'}")
            print(f"    Wilcoxon p : {stats['wilcoxon_p']:.4f}"
                  f"  {'✓' if stats['significant_wilcoxon'] else '—'}")
            print(f"    Permut.  p : {stats['perm_p']:.4f}"
                  f"  {'✓' if stats['significant_perm']     else '—'}")
            print()
    if not found:
        print("  Nenhuma combinação atingiu p<0.05.")
        print("  Verifique sensitivity analysis abaixo — threshold menor pode ter mais eventos.\n")

    # Bloco 5: sensitivity analysis
    if not sens_df.empty:
        print(f"{SEP2}")
        print("  SENSITIVITY ANALYSIS (h=10 barras):\n")
        print(f"  {'Thresh':>8}  {'Direção':<10}  {'N':>4}  {'WR':>7}  {'Exp(pts)':>9}")
        for _, row in sens_df[sens_df["n_events"] > 0].iterrows():
            if row["win_rate"] is None:
                continue
            print(f"  {row['threshold']:>7.0f}x  {row['direction']:<10}  "
                  f"{int(row['n_events']):>4}  {row['win_rate']:>7.1%}  "
                  f"{row['expectancy_pts']:>9.4f}")

    print(f"\n{SEP}")
    print("  CONCLUSÃO")
    print(SEP)
    print(f"""
  v2.1 corrige os 7 bugs originais e adiciona a camada M1:
  — classify_event() aplicado em load_and_prepare() → coluna event_type em todo o df
  — event_type propagado por extract_events() e compute_path_returns()
  — Análise cruzada event_direction × event_type disponível via path_df

  Próximo passo: se algum (direção, horizonte) tiver binom_p < 0.05 e
  expectancy_pts > 0, isolar esse subconjunto e testar walk-forward prospectivo.
""")
    print(SEP)


# ═══════════════════════════════════════════════════════════════════════════════
# 9. NEUTRAL ALPHA ISOLATION MODULE
# ═══════════════════════════════════════════════════════════════════════════════

def analyze_neutral_alpha(path_df: pd.DataFrame) -> None:
    """
    Isola e reporta o alpha condicional do subconjunto NEUTRAL.

    Filtros progressivos aplicados ao path_df existente:
      1. df_neutral       = event_direction == "NEUTRAL"
      2. df_neutral_high  = df_neutral where vol_regime == "HIGH"
      3. df_neutral_final = df_neutral_high where trend_regime == "RANGE"

    Por horizonte em HORIZONS: n, win rate, expectancy líquida.
    Sempre executa — imprime zeros/aviso se não houver dados.
    """
    SEP2 = "─" * 60

    print(f"\n  [NEUTRAL FILTERED ANALYSIS]")
    print(f"  {SEP2}")

    # path_df vazio ou sem coluna → reportar e sair graciosamente
    if path_df.empty or "event_direction" not in path_df.columns:
        print("  path_df vazio ou sem coluna event_direction.")
        print(f"  {SEP2}\n")
        return

    has_vol   = "vol_regime"   in path_df.columns
    has_trend = "trend_regime" in path_df.columns

    # ── Filtros progressivos ─────────────────────────────────────────────────
    df_neutral       = path_df[path_df["event_direction"] == "NEUTRAL"]
    df_neutral_high  = df_neutral[df_neutral["vol_regime"]   == "HIGH"]  if has_vol   else df_neutral
    df_neutral_final = df_neutral_high[df_neutral_high["trend_regime"] == "RANGE"] if has_trend else df_neutral_high

    n_neutral = df_neutral["event_time"].nunique()
    n_high    = df_neutral_high["event_time"].nunique()
    n_final   = df_neutral_final["event_time"].nunique()

    print(f"  total NEUTRAL events          : {n_neutral}")
    print(f"  HIGH VOL count                : {n_high}")
    print(f"  HIGH VOL + RANGE count        : {n_final}")
    print(f"  cost included                 : {COST_RT_EXTREME:.2f} pts RT")
    print(f"  {SEP2}")

    if n_neutral == 0:
        print("  No NEUTRAL events found.\n")
        return

    # ── Por horizonte ─────────────────────────────────────────────────────────
    for h in HORIZONS:
        sub = df_neutral_final[df_neutral_final["horizon"] == h]
        n   = len(sub)
        if n < 3:
            print(f"  [NEUTRAL h={h}] n={n} WR=n/a EXP=n/a  (insufficient)")
            continue

        wr  = float(sub["win"].mean())
        exp = float(sub["net_pts"].mean())
        flag = "  ← alpha candidate" if wr > 0.55 and exp > 0.0 else ""
        print(f"  [NEUTRAL h={h}] n={n} WR={wr:.1%} EXP={exp:+.4f}pts{flag}")

    # ── Salvar subset ─────────────────────────────────────────────────────────
    if not df_neutral_final.empty:
        out = OUTPUT_DIR / "neutral_alpha_subset.csv"
        df_neutral_final.to_csv(out, index=False)
        print(f"\n  subset saved: {out.name}")

    print(f"  {SEP2}\n")


# ═══════════════════════════════════════════════════════════════════════════════
# 10. WALK-FORWARD VALIDATION — NEUTRAL ALPHA
# ═══════════════════════════════════════════════════════════════════════════════

def walkforward_neutral_alpha(path_df: pd.DataFrame) -> None:
    """
    Walk-forward validation via expanding window (3 folds, sem sklearn).

    Problema de sparsity resolvido por dois mecanismos:

    1. FILTER TIERS — aplica o filtro mais restritivo que tenha eventos
       suficientes; relaxa automaticamente se não houver:
         Tier 1 (strict)  : NEUTRAL + (HIGH|MID) vol + RANGE trend
         Tier 2 (relaxed) : NEUTRAL + (HIGH|MID) vol  [sem filtro de trend]
         Tier 3 (fallback): NEUTRAL apenas

    2. EXPANDING WINDOW — agrega métricas de TODOS os horizontes do fold,
       não só de um único horizonte, maximizando dados por fold.

    Output: tabela fold_id | train_n | test_n | test_WR | test_EXP | train_EXP
    Consistency: alpha confirmado se ≥ 2/3 folds com test_exp > 0 E média > 0.
    """
    SEP2 = "─" * 66
    N_FOLDS          = 3
    MIN_EVENTS_TOTAL = N_FOLDS + 1   # mínimo absoluto para qualquer split

    print(f"\n  [WALK-FORWARD NEUTRAL ANALYSIS]")
    print(f"  {SEP2}")

    # ── Validação de entrada ──────────────────────────────────────────────────
    if path_df.empty or "event_direction" not in path_df.columns:
        print("  path_df vazio ou sem coluna event_direction — análise ignorada.")
        print(f"  {SEP2}\n")
        return

    if "event_time" not in path_df.columns:
        print("  Coluna event_time ausente — impossível ordenar cronologicamente.")
        print(f"  {SEP2}\n")
        return

    has_vol   = "vol_regime"   in path_df.columns
    has_trend = "trend_regime" in path_df.columns

    # ── Definição dos tiers de filtro ────────────────────────────────────────
    def _tier1(df: pd.DataFrame) -> pd.DataFrame:
        """NEUTRAL + (HIGH|MID) vol + RANGE trend"""
        out = df[df["event_direction"] == "NEUTRAL"]
        if has_vol:
            out = out[out["vol_regime"].isin(["HIGH", "MID"])]
        if has_trend:
            out = out[out["trend_regime"] == "RANGE"]
        return out

    def _tier2(df: pd.DataFrame) -> pd.DataFrame:
        """NEUTRAL + (HIGH|MID) vol  [RANGE relaxado]"""
        out = df[df["event_direction"] == "NEUTRAL"]
        if has_vol:
            out = out[out["vol_regime"].isin(["HIGH", "MID"])]
        return out

    def _tier3(df: pd.DataFrame) -> pd.DataFrame:
        """NEUTRAL apenas  [todos os regimes]"""
        return df[df["event_direction"] == "NEUTRAL"]

    # ── Selecionar tier com eventos suficientes ───────────────────────────────
    n1 = _tier1(path_df)["event_time"].nunique()
    n2 = _tier2(path_df)["event_time"].nunique()
    n3 = _tier3(path_df)["event_time"].nunique()

    print(f"  tier 1 (strict)  n_events={n1:>4}  [NEUTRAL + vol(H|M) + RANGE]")
    print(f"  tier 2 (relaxed) n_events={n2:>4}  [NEUTRAL + vol(H|M)]")
    print(f"  tier 3 (fallback)n_events={n3:>4}  [NEUTRAL]")

    if n1 >= MIN_EVENTS_TOTAL:
        apply_filter = _tier1
        tier_label   = "Tier 1 — NEUTRAL + (HIGH|MID) VOL + RANGE"
    elif n2 >= MIN_EVENTS_TOTAL:
        apply_filter = _tier2
        tier_label   = "Tier 2 — NEUTRAL + (HIGH|MID) VOL  [RANGE relaxado]"
    elif n3 >= MIN_EVENTS_TOTAL:
        apply_filter = _tier3
        tier_label   = "Tier 3 — NEUTRAL  [filtros relaxados]"
    else:
        print(f"\n  n_events insuficiente em todos os tiers (mínimo={MIN_EVENTS_TOTAL}).")
        print(f"  {SEP2}\n")
        return

    print(f"\n  filtro ativo: {tier_label}")
    print(f"  {SEP2}")

    # ── Expanding window: definir índices de fold ────────────────────────────
    # Obtém event_times únicos do subconjunto filtrado (cronológico)
    df_base     = apply_filter(path_df)
    event_times = sorted(df_base["event_time"].unique())
    n_events    = len(event_times)

    # Tamanho de cada janela de teste (eventos por fold)
    test_size = max(1, n_events // (N_FOLDS + 1))

    # Cada fold k: train=events[0..k*test_size], test=events[k*test_size..(k+1)*test_size]
    folds: list[tuple[int, int]] = []
    for k in range(1, N_FOLDS + 1):
        train_end  = k * test_size
        test_end   = (k + 1) * test_size if k < N_FOLDS else n_events
        if train_end >= n_events:
            break
        folds.append((train_end, test_end))

    actual_folds = len(folds)
    print(f"\n  expanding window — {actual_folds} fold(s), test_size≈{test_size} eventos/fold")
    print(f"  métricas: média ponderada de TODOS os horizontes com n≥3")

    # ── Helper: métricas agregadas (todos horizontes, n>=3) ──────────────────
    def _agg_metrics(df: pd.DataFrame) -> tuple[int, float, float]:
        """
        Agrega net_pts e win de TODOS os horizontes com n>=3.
        Retorna (n_events_únicos, mean_wr, mean_exp).
        """
        n_ev = df["event_time"].nunique()
        rows = []
        for h in HORIZONS:
            sub = df[df["horizon"] == h]
            if len(sub) >= 3:
                rows.append((float(sub["win"].mean()), float(sub["net_pts"].mean())))
        if not rows:
            return n_ev, float("nan"), float("nan")
        wr_mean  = float(np.mean([r[0] for r in rows]))
        exp_mean = float(np.mean([r[1] for r in rows]))
        return n_ev, wr_mean, exp_mean

    # ── Avaliar cada fold ─────────────────────────────────────────────────────
    print(f"\n  {'fold':>5}  {'train_n':>8}  {'test_n':>7}  "
          f"{'test_WR':>8}  {'test_EXP':>10}  {'train_EXP':>10}")
    print(f"  {SEP2}")

    fold_records: list[dict] = []

    for fold_idx, (train_end_idx, test_end_idx) in enumerate(folds):
        train_times = set(event_times[:train_end_idx])
        test_times  = set(event_times[train_end_idx:test_end_idx])

        df_train = df_base[df_base["event_time"].isin(train_times)]
        df_test  = df_base[df_base["event_time"].isin(test_times)]

        train_n, train_wr, train_exp = _agg_metrics(df_train)
        test_n,  test_wr,  test_exp  = _agg_metrics(df_test)

        # Formatação de cada campo
        def _fmt(val: float, fmt: str = "+.4f") -> str:
            return f"{val:{fmt}}" if not np.isnan(val) else "—"

        wr_str       = f"{test_wr:.1%}" if not np.isnan(test_wr)   else "n/a"
        test_exp_str = _fmt(test_exp)
        train_exp_str= _fmt(train_exp)

        print(f"  fold{fold_idx+1:>2}  {train_n:>8}  {test_n:>7}  "
              f"{wr_str:>8}  {test_exp_str:>10}  {train_exp_str:>10}")

        fold_records.append({
            "fold"     : fold_idx + 1,
            "train_n"  : train_n,
            "test_n"   : test_n,
            "test_wr"  : test_wr,
            "test_exp" : test_exp,
            "train_exp": train_exp,
        })

    # ── Consistency check ─────────────────────────────────────────────────────
    print(f"\n  {SEP2}")

    valid = [r for r in fold_records if not np.isnan(r["test_exp"])]

    if not valid:
        print("  Nenhum fold com dados suficientes para consistency check.")
        print(f"  {SEP2}\n")
        return

    n_valid    = len(valid)
    n_positive = sum(1 for r in valid if r["test_exp"] > 0)
    mean_exp   = float(np.mean([r["test_exp"] for r in valid]))
    threshold  = max(2, int(np.ceil(n_valid * 0.67)))   # ≥ 67% folds positivos

    print(f"  folds válidos   : {n_valid}/{actual_folds}")
    print(f"  folds positivos : {n_positive}/{n_valid}  (threshold={threshold})")
    print(f"  test exp médio  : {mean_exp:+.4f} pts")
    print()

    if n_positive >= threshold and mean_exp > 0:
        print("  → ALPHA CONFIRMED (ROBUST)")
        print(f"    {n_positive}/{n_valid} folds com test_exp > 0 e média positiva.")
    else:
        print("  → ALPHA NOT ROBUST (LIKELY OVERFIT)")
        if n_positive < n_valid // 2:
            print(f"    Maioria dos folds com expectancy negativa ({n_positive}/{n_valid} positivos).")
        elif mean_exp <= 0:
            print(f"    Folds positivos mas média geral negativa — instabilidade.")
        else:
            print(f"    Folds positivos insuficientes ({n_positive}/{n_valid} < {threshold} exigidos).")

    print(f"  {SEP2}\n")


# ═══════════════════════════════════════════════════════════════════════════════
# 11. MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    print("=" * 72)
    print("  EXTREME EVENT ANALYSIS v2.4")
    print("  WDO-EVOLVED-QUANT | Fase 2 | BUG-01–07 + M1 + M2 + STRATEGY + FEATURE GRID")
    print("=" * 72)

    # [1] Carga e preparação (inclui M1 e M2)
    print(f"\n[1/10] Carregando dados de {DATA_PATH.name}...")
    df = load_and_prepare(DATA_PATH)
    print(f"      {len(df):,} barras | {df['datetime'].iloc[0]} → {df['datetime'].iloc[-1]}")
    print(f"      volume_ma: rolling({VOL_LOOKBACK}, shift=1) — BUG-04 corrigido")
    if "event_type" in df.columns:
        dist = df["event_type"].value_counts()
        print(f"      M1 event_type  : {dict(dist)}")
    if "vol_regime" in df.columns:
        print(f"      M2 vol_regime  : {dict(df['vol_regime'].value_counts())}")
        print(f"      M2 trend_regime: {dict(df['trend_regime'].value_counts())}")
        print(f"      M2 session     : {dict(df['session_regime'].value_counts())}")

    # [2] Split OOS
    print("\n[2/10] Split OOS (80% treino / 20% teste)...")
    split_date = df["datetime"].quantile(0.8)
    _, test = split_out_of_sample(df, split_date)
    test = test.reset_index(drop=True)
    print(f"      Teste: {test['datetime'].iloc[0]} → {test['datetime'].iloc[-1]}")
    print(f"      {len(test):,} barras no conjunto de teste")

    # [3] Extração de eventos com clustering filter
    print(f"\n[3/10] Extraindo eventos (threshold={DEFAULT_THRESHOLD}x, "
          f"gap≥{MIN_EVENT_GAP} barras)...")
    events = extract_events(test, DEFAULT_THRESHOLD)
    n_total = len(events)

    if n_total == 0:
        print("      AVISO: nenhum evento encontrado. Verificar sensitivity analysis.")
    else:
        by_dir = events["event_direction"].value_counts().to_dict()
        print(f"      {n_total} eventos independentes:")
        for d in ("BULLISH", "BEARISH", "NEUTRAL"):
            n_d = by_dir.get(d, 0)
            print(f"        {d:<10}: {n_d} ({n_d/n_total:.1%})")
        if "event_type" in events.columns:
            by_type = events["event_type"].value_counts().to_dict()
            print(f"      M1 tipos: {by_type}")

        out_ev = OUTPUT_DIR / "extreme_events_v2_classified.csv"
        cols = [
            "datetime", "volume_rel", "event_direction", "event_type",
            "vol_regime", "trend_regime", "session_regime",
            "body_ratio", "buying_pressure",
        ]
        events[[c for c in cols if c in events.columns]].to_csv(out_ev, index=False)
        print(f"      Eventos salvos: {out_ev.name}")

    # [4] Path analysis
    print(f"\n[4/10] Path analysis — horizontes {HORIZONS} barras...")
    if n_total > 0:
        path_df = compute_path_returns(test, events, HORIZONS)
        out_path = OUTPUT_DIR / "extreme_events_v2_path.csv"
        path_df.to_csv(out_path, index=False)
        print(f"      {len(path_df)} registros | salvo: {out_path.name}")
    else:
        path_df = pd.DataFrame()
        print("      Sem eventos — path analysis ignorada")

    # [5] Testes estatísticos
    print("\n[5/10] Testes estatísticos (binomial + Wilcoxon + permutação)...")
    stat_results: dict = {}
    if not path_df.empty:
        for direction in ("BULLISH", "BEARISH", "NEUTRAL"):
            for h in HORIZONS:
                key   = (direction, h)
                stats = run_statistical_tests(path_df, direction, h)
                stat_results[key] = stats
                if not stats.get("insufficient"):
                    sig = " ★" if (stats["significant_binom"] or
                                    stats["significant_wilcoxon"]) else ""
                    print(f"      [{direction:<8} h={h:2d}]{sig:<2}  "
                          f"n={stats['n']:2d}  WR={stats['win_rate']:.0%}  "
                          f"exp={stats['expectancy_pts']:+.3f}pts  "
                          f"binom_p={stats['binom_p']:.3f}")
    else:
        print("      Sem dados para testar")

    # [6/10] NEUTRAL FILTERED ANALYSIS
    print("\n[6/10] NEUTRAL FILTERED ANALYSIS")
    analyze_neutral_alpha(path_df)

    # [7/10] STRATEGY VALIDATION — NEUTRAL ALPHA (sklearn TimeSeriesSplit)
    print("\n[7/10] NEUTRAL STRATEGY VALIDATION")
    run_strategy_validation(test, events, OUTPUT_DIR, n_folds=3)

    # [8/10] Sensitivity analysis + gráficos
    print(f"\n[8/10] Sensitivity analysis — thresholds {THRESHOLDS}x...")
    sens_df = sensitivity_analysis(test, THRESHOLDS)
    if not sens_df.empty:
        out_sens = OUTPUT_DIR / "extreme_events_v2_sensitivity.csv"
        sens_df.to_csv(out_sens, index=False)
        sub = sens_df[sens_df["n_events"] > 0][
            ["threshold", "direction", "n_events", "win_rate", "expectancy_pts"]
        ]
        print(sub.to_string(index=False))

    print("      Gerando gráficos...")
    if not path_df.empty:
        plot_path_by_direction(path_df, OUTPUT_DIR / "extreme_events_v2_path.png")
    if n_total > 0:
        plot_event_type_distribution(events, OUTPUT_DIR / "extreme_events_v2_m1_distribution.png")
    if not sens_df.empty:
        plot_sensitivity(sens_df, OUTPUT_DIR / "extreme_events_v2_sensitivity.png")

    # [9/10] Relatório comparativo
    print("\n[9/10] Relatório comparativo:")
    n_by_dir = events["event_direction"].value_counts().to_dict() if n_total > 0 else {}
    print_comparison_report(n_total, n_by_dir, stat_results, sens_df, events)

    # [10/10] FEATURE GRID SEARCH — dataset completo (treino + teste)
    print("\n[10/10] FEATURE GRID SEARCH")
    print("  Computando path_df sobre dataset COMPLETO para maximizar amostra...")
    all_events_full = extract_events(df, DEFAULT_THRESHOLD)
    if not all_events_full.empty:
        path_df_full = compute_path_returns(df, all_events_full, HORIZONS)
        print(f"  path_df_full: {len(path_df_full):,} linhas "
              f"({all_events_full['event_direction'].value_counts().to_dict()})")
        run_feature_research(path_df_full, OUTPUT_DIR)
    else:
        print("  Nenhum evento no dataset completo — feature research ignorada.")


if __name__ == "__main__":
    main()
