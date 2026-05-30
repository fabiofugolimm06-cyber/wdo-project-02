import pandas as pd
import numpy as np

arquivo = "WDOFUT_F_0_1min.csv"

df = pd.read_csv(arquivo, sep=r'\s+', header=None,
                 names=['ativo','dia','mes','ano','hora','minuto','segundo',
                        'abertura','maxima','minima','fechamento','volume','negocios'])

for col in ['abertura','maxima','minima','fechamento']:
    df[col] = df[col].astype(str).str.replace(' ', '.', regex=False).astype(float)

df['volume'] = df['volume'].astype(str).str.replace(' ', '.', regex=False).astype(float)

# Criar datetime manualmente
df['datetime'] = pd.to_datetime(
    df['ano'].astype(str) + '-' + df['mes'].astype(str) + '-' + df['dia'].astype(str) + ' ' +
    df['hora'].astype(str) + ':' + df['minuto'].astype(str) + ':' + df['segundo'].astype(str),
    format='%Y-%m-%d %H:%M:%S'
)

df = df.sort_values('datetime')

print(df[['datetime','abertura','maxima','minima','fechamento','volume']].head())
print("\n=== Estatísticas ===")
print(df[['fechamento','volume']].describe())