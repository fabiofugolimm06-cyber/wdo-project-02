import pandas as pd
from typing import Tuple

def split_out_of_sample(
    df: pd.DataFrame,
    train_end_date: str,
    test_start_date: str = None
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    df = df.sort_values('datetime')
    if test_start_date is None:
        test_start_date = train_end_date
    train = df[df['datetime'] < train_end_date].copy()
    test = df[df['datetime'] >= test_start_date].copy()
    return train, test
