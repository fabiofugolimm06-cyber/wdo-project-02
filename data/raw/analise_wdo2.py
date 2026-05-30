import pandas as pd
import numpy as np

arquivo = "WDOFUT_F_0_1min.csv"

# Lê o CSV com separador ponto e vírgula
df = pd.read_csv(arquivo, sep=';', header=None,
                 names=['ativo','data','hora','abertura','maxima','minima','fechamento','volume','negocios'])

# Converte a coluna data+hora em datetime
df['datetime'] = pd.to_datetime(df['data'] + ' ' + df['hora'], format='%d/%m/%Y %H:%M:%S')

# Converte preços e volume (trocando vírgula por ponto)
for col in ['abertura','maxima','minima','fechamento','volume']:
    df[col] = df[col].str.replace(',', '.').astype(float)

df = df.sort_values('datetime')

print(df[['datetime','abertura','maxima','minima','fechamento','volume']].head())
print("\n=== Estatísticas dos preços de fechamento e volume ===")
print(df[['fechamento','volume']].describe())