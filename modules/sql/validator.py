# modules/sql/validator.py
import pandas as pd

def normalize(df):
    return df.sort_index(axis=1).sort_values(by=list(df.columns)).reset_index(drop=True)

def validate(result, expected):
    try:
        expected_df = pd.DataFrame(expected)
        return normalize(result).equals(normalize(expected_df))
    except:
        return False