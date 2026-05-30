import pandas as pd
import numpy as np

from microstructure.features.registry import register_feature
from microstructure.features.base import BaseFeature


@register_feature
class RangeFeature(BaseFeature):

    name = "range"
    version = "1.0"
    causal = True
    warmup_bars = 0
    dtype = "float32"
    group = "structural"

    input_cols = ("alta", "baixa")

    def _compute_impl(self, df: pd.DataFrame) -> pd.Series:
        return (df["alta"] - df["baixa"]).astype(np.float32)
