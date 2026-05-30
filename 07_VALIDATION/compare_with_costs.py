import pandas as pd
from pathlib import Path

def aggregate_to_timeframe(df: pd.DataFrame, freq: str = '5min') -> pd.DataFrame:
    """Agrega dados de 1 minuto para timeframe superior (ex: 5min, 15min)."""
    df = df.copy()
    df.set_index('datetime', inplace=True)
    ohlc = df.resample(freq).agg({
        'abertura': 'first',
        'máxima': 'max',
        'mínima': 'min',
        'fechamento': 'last',
        'volume': 'sum'
    }).dropna()
    ohlc.reset_index(inplace=True)
    return ohlc

def main():
    data_path = Path(r"C:\Users\fabio\Desktop\Projetos\WDO PROJECT 02\data\raw\WDOFUT_processado.parquet")
    df = pd.read_parquet(data_path)
    df['datetime'] = pd.to_datetime(df['datetime'])
    df.sort_values('datetime', inplace=True)
    
    # Renomear colunas para o padrão do framework
    if 'maxima' in df.columns:
        df.rename(columns={'maxima': 'máxima', 'minima': 'mínima'}, inplace=True)
    
    # Agregação para 5 minutos
    df_5min = aggregate_to_timeframe(df, '5min')
    print(f"Dados originais: {len(df)} registros")
    print(f"Dados agregados (5min): {len(df_5min)} registros")
    
    # Salvar
    output_path = Path(r"C:\Users\fabio\Desktop\Projetos\WDO PROJECT 02\data\raw\WDOFUT_5min.parquet")
    df_5min.to_parquet(output_path, index=False)
    print(f"Arquivo salvo em {output_path}")

if __name__ == "__main__":
    main()