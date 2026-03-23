# modules/sql/validator.py
import pandas as pd


def normalize(df):
    normalized = df.copy()

    for column in normalized.columns:
        numeric_values = pd.to_numeric(normalized[column], errors="coerce")

        if numeric_values.notna().all():
            normalized[column] = numeric_values.astype(float)

    return normalized.sort_index(axis=1).sort_values(by=list(normalized.columns)).reset_index(drop=True)


def validate(result, expected):
    try:
        expected_df = pd.DataFrame(expected)
        return normalize(result).equals(normalize(expected_df))
    except Exception:
        return False
