import pandas as pd
import numpy as np
from strategy_base import StrategyBase   # <-- LINHA ESSENCIAL

class BreakoutDonchian20(StrategyBase):
    def __init__(self):
        super().__init__(name="BreakoutDonchian20", params={"lookback": 20})
    
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        lookback = self.params["lookback"]
        df['max_high'] = df['máxima'].rolling(lookback).max()
        df['min_low'] = df['mínima'].rolling(lookback).min()
        df['sinal'] = 0
        df.loc[df['fechamento'] > df['max_high'].shift(1), 'sinal'] = 1
        df.loc[df['fechamento'] < df['min_low'].shift(1), 'sinal'] = -1
        df['posicao'] = df['sinal'].shift(1).fillna(0)
        return df

class BollingerMeanReversion20(StrategyBase):
    def __init__(self):
        super().__init__(name="BollingerMeanReversion20", params={"window": 20, "num_std": 2})
    
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        window = self.params["window"]
        num_std = self.params["num_std"]
        df['ma'] = df['fechamento'].rolling(window).mean()
        df['std'] = df['fechamento'].rolling(window).std()
        df['upper'] = df['ma'] + (df['std'] * num_std)
        df['lower'] = df['ma'] - (df['std'] * num_std)
        df['sinal'] = 0
        df.loc[df['fechamento'] < df['lower'], 'sinal'] = 1
        df.loc[df['fechamento'] > df['upper'], 'sinal'] = -1
        df['posicao'] = df['sinal'].shift(1).fillna(0)
        return df

class TimeSessionBiasStrategy(StrategyBase):
    def __init__(self):
        super().__init__(name="TimeSessionBiasStrategy", params={
            "morning_start": 10, "morning_end": 12, "morning_end_min": 30,
            "afternoon_start": 14, "afternoon_end": 16, "afternoon_end_min": 0
        })
    
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        hour = df['datetime'].dt.hour
        minute = df['datetime'].dt.minute
        morning = ((hour >= self.params["morning_start"]) & (hour < self.params["morning_end"])) | \
                  ((hour == self.params["morning_end"]) & (minute <= self.params["morning_end_min"]))
        afternoon = ((hour >= self.params["afternoon_start"]) & (hour < self.params["afternoon_end"])) | \
                    ((hour == self.params["afternoon_end"]) & (minute <= self.params["afternoon_end_min"]))
        df['posicao'] = 0
        df.loc[morning, 'posicao'] = 1
        df.loc[afternoon, 'posicao'] = -1
        return df

class BreakoutDonchianWithVolume(StrategyBase):
    """
    Donchian breakout com confirmação de volume:
    Compra quando fechamento > máxima de 20 períodos E volume > média(volume, 20)
    Venda quando fechamento < mínima de 20 períodos E volume > média(volume, 20)
    """
    def __init__(self):
        super().__init__(name="BreakoutDonchianWithVolume", params={"lookback": 20, "volume_lookback": 20})
    
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        lookback = self.params["lookback"]
        vol_lookback = self.params["volume_lookback"]
        
        df['max_high'] = df['máxima'].rolling(lookback).max()
        df['min_low'] = df['mínima'].rolling(lookback).min()
        df['volume_ma'] = df['volume'].rolling(vol_lookback).mean()
        
        df['sinal'] = 0
        buy_signal = (df['fechamento'] > df['max_high'].shift(1)) & (df['volume'] > df['volume_ma'].shift(1))
        sell_signal = (df['fechamento'] < df['min_low'].shift(1)) & (df['volume'] > df['volume_ma'].shift(1))
        
        df.loc[buy_signal, 'sinal'] = 1
        df.loc[sell_signal, 'sinal'] = -1
        df['posicao'] = df['sinal'].shift(1).fillna(0)
        return df