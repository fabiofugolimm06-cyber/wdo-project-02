import pandas as pd
import numpy as np

from microstructure.features.registry import register_feature
from microstructure.features.base import BaseFeature


@register_feature
class ReturnsFeature(BaseFeature):

    name = "returns"
    version = "1.0"
    causal = True
    warmup_bars = 0
    dtype = "float32"
    group = "structural"

    input_cols = ("abertura", "fechamento")

    def _compute_impl(self, df: pd.DataFrame) -> pd.Series:
        abertura = df["abertura"].astype(np.float64)
        ret = (df["fechamento"] - abertura) / abertura.replace(0, np.nan)
        return ret.astype(np.float32)
