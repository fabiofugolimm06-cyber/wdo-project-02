import pandas as pd
import numpy as np

from microstructure.features.registry import register_feature
from microstructure.features.base import BaseFeature


@register_feature
class DeltaFeature(BaseFeature):

    name = "delta"
    version = "1.0"
    causal = True
    warmup_bars = 0
    dtype = "float32"
    group = "structural"

    input_cols = ("abertura", "fechamento")

    def _compute_impl(self, df: pd.DataFrame) -> pd.Series:
        return (df["fechamento"] - df["abertura"]).astype(np.float32)