import pandas as pd
import numpy as np

from microstructure.features.registry import register_feature
from microstructure.features.base import BaseFeature


@register_feature
class VolumeZScoreFeature(BaseFeature):

    name = "volume_zscore"
    version = "1.0"
    causal = True
    warmup_bars = 20
    dtype = "float32"
    group = "structural"

    input_cols = ("volume",)

    window: int = 20

    def _compute_impl(self, df: pd.DataFrame) -> pd.Series:
        vol = df["volume"].astype(np.float64)
        # min_periods=1: causal; evita 19 barras NaN (window-1) no ML após horizon=5
        roll = vol.rolling(window=self.window, min_periods=1)
        mean = roll.mean()
        std = roll.std(ddof=0).replace(0, np.nan)
        z = (vol - mean) / std
        return z.fillna(0.0).astype(np.float32)
