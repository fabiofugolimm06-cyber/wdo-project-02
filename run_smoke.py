import pandas as pd
import numpy as np
from 08_MICROSTRUCTURE.features.datasets import build_dataset

df = pd.DataFrame({
    'abertura': np.random.randn(200),
    'fechamento': np.random.randn(200),
    'alta': np.random.randn(200),
    'baixa': np.random.randn(200),
}, index=pd.date_range('2024-01-01', periods=200))

X = build_dataset(df).X

print(X.shape)
print(X.dtypes)
