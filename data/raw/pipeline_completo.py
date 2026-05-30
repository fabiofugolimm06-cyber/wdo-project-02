import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import os

print("Configurando ambiente...")
os.makedirs('output', exist_ok=True)
os.makedirs('graficos', exist_ok=True)

print("Lendo arquivo...")
arquivo = "WDOFUT_F_0_1min.csv"

# Leitura sem parse_dates para evitar erro
df = pd.read_csv(arquivo, sep=';', decimal=',', header=None,
                 names=['ativo','data','hora','abertura','maxima','minima','fechamento','volume','negocios'])

# Remove a coluna 'ativo' (não necessária)
df.drop('ativo', axis=1, inplace=True)

# Cria uma coluna datetime combinando data e hora
df['datetime'] = pd.to_datetime(df['data'] + ' ' + df['hora'], dayfirst=True)

# Remove as colunas data e hora originais
df.drop(['data','hora'], axis=1, inplace=True)

# Reordena as colunas
df = df[['datetime','abertura','maxima','minima','fechamento','volume','negocios']]

# Ordena por tempo
df = df.sort_values('datetime').reset_index(drop=True)

print(f"Carregados {len(df):,} registros. Período: {df['datetime'].min()} a {df['datetime'].max()}")

# Calcula retorno logarítmico
df['ret_log'] = np.log(df['fechamento'] / df['fechamento'].shift(1))

# Média móvel de 20 períodos
df['MM20'] = df['fechamento'].rolling(20).mean()

print("\n=== Estatísticas do fechamento ===")
print(df['fechamento'].describe())

print("\n=== Top 10 maiores volumes (minuto) ===")
print(df.nlargest(10, 'volume')[['datetime','fechamento','volume']])

print("\n=== Salvando gráfico... ===")
plt.figure(figsize=(14,5))
plt.plot(df['datetime'], df['fechamento'], linewidth=0.5, label='Fechamento')
plt.plot(df['datetime'], df['MM20'], linewidth=1, label='MM20 (20 períodos)', color='orange')
plt.title('WDOFUT - Preço de fechamento e Média Móvel 20 períodos')
plt.xlabel('Data/Hora')
plt.ylabel('Pontos')
plt.legend()
plt.grid(True)
plt.savefig('graficos/preco_mm20.png')
plt.close()   # Fecha a figura para não ocupar memória
print("Gráfico salvo em 'graficos/preco_mm20.png'")

# Exporta dados processados
df.to_parquet('WDOFUT_processado.parquet')
print("Dados salvos em 'WDOFUT_processado.parquet'")

# Salva também uma versão CSV reduzida (apenas OHLCV)
df_ohlc = df[['datetime','abertura','maxima','minima','fechamento','volume']]
df_ohlc.to_csv('WDOFUT_OHLC.csv', index=False)
print("Versão OHLCV salva em 'WDOFUT_OHLC.csv'")

print("\n=== Pipeline concluído com sucesso! ===")