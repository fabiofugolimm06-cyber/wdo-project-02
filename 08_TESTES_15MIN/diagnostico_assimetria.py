import pandas as pd
import numpy as np

# Tenta ler o arquivo de trades se existir
try:
    trades_df = pd.read_csv("trades_15min.csv")
    print("📂 Lendo trades do arquivo trades_15min.csv")
    
    # Calcula PnL líquido com custos
    SLIPPAGE_POINTS = 0.5
    COMMISSION_BRL = 0.30
    POINT_VALUE = 10.0
    cost_pts = SLIPPAGE_POINTS + (COMMISSION_BRL / POINT_VALUE)
    
    trades = []
    for idx, row in trades_df.iterrows():
        direction = row['direction']
        entry = row['entry_price']
        exit_ = row['exit_price']
        
        if direction == 1:
            raw = exit_ - entry
        else:
            raw = entry - exit_
        
        net = raw - cost_pts
        trades.append(net)
    
    trades = np.array(trades)
    
except FileNotFoundError:
    print("⚠️ Arquivo trades_15min.csv não encontrado.")
    print("Usando dados de exemplo (substitua pelos valores reais dos 52 trades)")
    
    # SUBSTITUA ESTES VALORES PELOS SEUS 52 TRADES REAIS
    trades = np.array([
        -1.2, -0.8, 0.5, -2.1, 1.3, -0.4, -0.9, 0.2, -1.5, 0.7,
        -0.3, 1.1, -1.8, 0.4, -0.6, 0.9, -2.0, 1.5, -0.7, 0.3,
        -1.1, 0.8, -1.4, 0.6, -0.5, 1.2, -1.9, 0.1, -0.2, 1.4,
        -1.6, 0.5, -0.8, 1.0, -1.3, 0.7, -0.4, 1.6, -1.0, 0.2,
        -0.9, 1.1, -1.7, 0.4, -0.6, 1.3, -1.2, 0.8, -0.3, 1.0,
        -0.5, 0.6
    ])

print("="*50)
print("DIAGNÓSTICO DE ASSIMETRIA - Donchian 15min")
print("="*50)
print(f"Total de trades: {len(trades)}")
print(f"Expectancy líquida: {trades.mean():.2f} pontos")
print(f"Win rate: {(trades > 0).mean():.1%}")

winners = trades[trades > 0]
losers = trades[trades < 0]

print(f"\n--- Winners ---")
print(f"Quantidade: {len(winners)}")
print(f"Médio: {winners.mean():.2f} pts")
print(f"Mediano: {np.median(winners):.2f} pts")

print(f"\n--- Losers ---")
print(f"Quantidade: {len(losers)}")
print(f"Médio: {losers.mean():.2f} pts")
print(f"Mediano: {np.median(losers):.2f} pts")

if len(winners) > 0 and len(losers) > 0:
    ratio = abs(losers.mean() / winners.mean())
    print(f"\n--- Razão perda média / ganho médio: {ratio:.2f} ---")
    
    if ratio > 1.5:
        print("⚠️ PERDAS MÉDIAS SÃO MUITO MAIORES QUE GANHOS")
        print("   -> Problema de CAUDA ESQUERDA")
        print("   -> Solução: stop-loss mais agressivo")
    elif ratio < 0.7:
        print("⚠️ GANHOS MÉDIOS SÃO MUITO MAIORES QUE PERDAS")
        print("   -> Problema de WIN RATE BAIXO")
        print("   -> Solução: melhorar precisão dos sinais")
    else:
        print("✅ GANHOS E PERDAS PROPORCIONAIS")

print(f"\n--- Distribuição ---")
print(f"Percentil 95: {np.percentile(trades, 95):.2f} pts")
print(f"Percentil 90: {np.percentile(trades, 90):.2f} pts")
print(f"Percentil 10: {np.percentile(trades, 10):.2f} pts")
print(f"Percentil 5: {np.percentile(trades, 5):.2f} pts")
print(f"Pior trade: {trades.min():.2f} pts")
print(f"Melhor trade: {trades.max():.2f} pts")

# Verifica cauda extrema
if len(losers) > 0:
    avg_loss = abs(losers.mean())
    worst_loss = abs(trades.min())
    if worst_loss > 3 * avg_loss:
        print(f"\n⚠️ CAUDA EXTREMA: pior perda ({worst_loss:.2f}) > 3x perda média ({avg_loss:.2f})")
        print("   -> Considere stop-loss fixo de 3-4 pontos")