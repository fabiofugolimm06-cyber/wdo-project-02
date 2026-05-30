"""
wdo_15min_correcao.py
Testa estratégias simples no WDO em timeframe 15min, com custos reais e walk-forward.
NÃO depende de módulos antigos - é 100% autônomo.
"""

import pandas as pd
import numpy as np
from pathlib import Path

# ================= CONFIGURAÇÕES =================
# >>>>> AJUSTE O CAMINHO DO CSV CONFORME SUA ESTRUTURA <<<<<
INPUT_CSV = r"..\data\raw\WDOFUT_OHLC.csv"   # exemplo: pasta acima tem data/raw/
# Se preferir copiar o CSV para a mesma pasta, use: INPUT_CSV = "WDOFUT_OHLC.csv"
# Ou caminho absoluto: r"C:\Users\fabio\Desktop\Projetos\WDO PROJECT 02\data\raw\WDOFUT_OHLC.csv"

SEP = ';'
DECIMAL = ','
DATE_COL = 'datetime'   # ou 'Date' se for o caso
PRICE_COL = 'close'
VOLUME_COL = 'volume'

# Custos (mini dólar: 1 ponto = R$10)
SLIPPAGE_POINTS = 0.5
COMMISSION_BRL = 0.30
POINT_VALUE = 10.0

# Walk-forward: treino 3 meses (~1800 barras 15min), teste 1 mês (~600)
TRAIN_BARS = 1800
TEST_BARS = 600

# Parâmetros das estratégias
DONCHIAN_LOOKBACK = 20
BOLLINGER_WINDOW = 20
BOLLINGER_STD = 2.0
VOLUME_THRESHOLD = 1.5
VOLATILITY_REGIME_THRESHOLD = 0.8   # só opera se volatilidade < 80% da média
# =================================================

def load_data(csv_path):
    """Carrega CSV com separador ; e vírgula decimal."""
    df = pd.read_csv(csv_path, sep=SEP, decimal=DECIMAL, parse_dates=[DATE_COL])
    # Se houver colunas Date e Time separadas, combine:
    if 'Date' in df.columns and 'Time' in df.columns:
        df['datetime'] = pd.to_datetime(df['Date'] + ' ' + df['Time'])
    df.set_index('datetime', inplace=True)
    df.sort_index(inplace=True)
    return df

def aggregate_to_15min(df_1min):
    """Agrega dados de 1 minuto para 15 minutos."""
    ohlc = {
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    }
    df_15min = df_1min.resample('15T').agg(ohlc).dropna()
    return df_15min

def compute_indicators(df):
    """Calcula indicadores para as estratégias."""
    df = df.copy()
    # Donchian
    df['donchian_high'] = df['high'].rolling(DONCHIAN_LOOKBACK).max()
    df['donchian_low'] = df['low'].rolling(DONCHIAN_LOOKBACK).min()
    # Bollinger
    df['bb_mid'] = df['close'].rolling(BOLLINGER_WINDOW).mean()
    df['bb_std'] = df['close'].rolling(BOLLINGER_WINDOW).std()
    df['bb_upper'] = df['bb_mid'] + BOLLINGER_STD * df['bb_std']
    df['bb_lower'] = df['bb_mid'] - BOLLINGER_STD * df['bb_std']
    # Volume médio
    df['volume_ma'] = df['volume'].rolling(DONCHIAN_LOOKBACK).mean()
    # Volatilidade (retornos absolutos)
    df['returns'] = df['close'].pct_change().abs()
    df['vol_ma'] = df['returns'].rolling(DONCHIAN_LOOKBACK).mean()
    return df

def donchian_signal(df, idx):
    """1 = comprar (breakout alta), -1 = vender (breakout baixa), 0 = nada."""
    if pd.isna(df.loc[idx, 'donchian_high']) or pd.isna(df.loc[idx, 'donchian_low']):
        return 0
    close = df.loc[idx, 'close']
    high = df.loc[idx, 'donchian_high']
    low = df.loc[idx, 'donchian_low']
    if close > high:
        return 1
    elif close < low:
        return -1
    return 0

def bollinger_signal(df, idx):
    """Reversão: acima da banda superior vende, abaixo compra."""
    if pd.isna(df.loc[idx, 'bb_upper']):
        return 0
    close = df.loc[idx, 'close']
    upper = df.loc[idx, 'bb_upper']
    lower = df.loc[idx, 'bb_lower']
    if close > upper:
        return -1
    elif close < lower:
        return 1
    return 0

def donchian_volume_signal(df, idx):
    """Donchian + volume > threshold."""
    sig = donchian_signal(df, idx)
    if sig == 0:
        return 0
    vol = df.loc[idx, 'volume']
    vol_ma = df.loc[idx, 'volume_ma']
    if pd.isna(vol_ma) or vol_ma == 0:
        return 0
    if vol / vol_ma > VOLUME_THRESHOLD:
        return sig
    return 0

def regime_vol_signal(df, idx):
    """Donchian + baixa volatilidade (volatilidade atual < threshold * média)."""
    sig = donchian_signal(df, idx)
    if sig == 0:
        return 0
    vol = df.loc[idx, 'returns']
    vol_ma = df.loc[idx, 'vol_ma']
    if pd.isna(vol_ma) or vol_ma == 0:
        return 0
    if vol < VOLATILITY_REGIME_THRESHOLD * vol_ma:
        return sig
    return 0

def compute_trade_metrics(trades, prices):
    """Calcula expectancy líquida (pontos)."""
    if not trades:
        return None
    net_points = []
    for t in trades:
        entry_price = t['entry_price']
        exit_price = t['exit_price']
        direction = t['direction']
        if direction == 1:  # long
            raw_points = exit_price - entry_price
        else:  # short
            raw_points = entry_price - exit_price
        # custos
        cost_pts = SLIPPAGE_POINTS + (COMMISSION_BRL / POINT_VALUE)
        net_pts = raw_points - cost_pts
        net_points.append(net_pts)
    expectancy = np.mean(net_points)
    win_rate = np.sum(np.array(net_points) > 0) / len(net_points)
    total_trades = len(net_points)
    return {'expectancy_points': expectancy, 'win_rate': win_rate, 'total_trades': total_trades}

def walk_forward(df_15min, strategy_func):
    """Executa walk-forward simples."""
    trades = []
    n = len(df_15min)
    for start in range(0, n - TRAIN_BARS - TEST_BARS, TEST_BARS):
        train_end = start + TRAIN_BARS
        test_end = train_end + TEST_BARS
        if test_end > n:
            break
        # Treino (apenas para calcular indicadores - como são rolling, usamos dados completos até test_end)
        # Na prática, indicadores já estão calculados. Fazemos simulação dentro do periodo de teste.
        df_test = df_15min.iloc[train_end:test_end].copy()
        position = 0
        entry_price = 0
        for i in range(len(df_test)):
            idx = df_test.index[i]
            # Pega sinal baseado nos dados até o momento (rolling inclui histórico)
            signal = strategy_func(df_15min.loc[:idx], idx)  # usa dados até o momento
            if position == 0 and signal != 0:
                position = signal
                entry_price = df_test.loc[idx, 'close']
            elif position != 0 and signal == -position:
                exit_price = df_test.loc[idx, 'close']
                trades.append({
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'direction': position
                })
                position = 0
        # Fecha posição remanescente no fim do período
        if position != 0:
            exit_price = df_test.iloc[-1]['close']
            trades.append({
                'entry_price': entry_price,
                'exit_price': exit_price,
                'direction': position
            })
    return trades

def main():
    print("📁 Carregando dados 1min...")
    try:
        df_1min = load_data(INPUT_CSV)
    except FileNotFoundError:
        print(f"❌ Arquivo não encontrado: {INPUT_CSV}")
        print("   Ajuste a variável INPUT_CSV no script.")
        return
    print(f"   Registros originais: {len(df_1min)} (1min)")
    
    print("🕒 Agregando para 15min...")
    df_15min = aggregate_to_15min(df_1min)
    print(f"   Registros agregados: {len(df_15min)} (15min)")
    
    print("📊 Calculando indicadores...")
    df_15min = compute_indicators(df_15min)
    
    strategies = {
        'Donchian': donchian_signal,
        'Bollinger': bollinger_signal,
        'Donchian+Volume': donchian_volume_signal,
        'Regime (baixa vol)': regime_vol_signal
    }
    
    print("\n🚀 Executando walk-forward com custos reais...\n")
    results = {}
    for name, func in strategies.items():
        trades = walk_forward(df_15min, func)
        metrics = compute_trade_metrics(trades, df_15min['close'])
        if metrics:
            results[name] = metrics
            print(f"{name:20} | Expectancy: {metrics['expectancy_points']:7.2f} pts | Win Rate: {metrics['win_rate']*100:5.1f}% | Trades: {metrics['total_trades']}")
        else:
            print(f"{name:20} | Nenhum trade gerado")
    
    # Salvar resultados em CSV
    output_path = Path("resultados_15min.csv")
    if results:
        df_res = pd.DataFrame(results).T
        df_res.to_csv(output_path)
        print(f"\n✅ Resultados salvos em {output_path.absolute()}")
    else:
        print("\n⚠️ Nenhuma estratégia gerou trades.")

if __name__ == "__main__":
    main()
