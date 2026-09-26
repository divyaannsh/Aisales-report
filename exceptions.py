"""
Exception detection module for AI Sales Exception Reporter.

Flags rows where sales targets were missed based on a configurable percentage threshold.
"""

import pandas as pd
from typing import Optional


def flag_exceptions(df: pd.DataFrame, threshold_pct: float = 90.0) -> pd.DataFrame:
    """
    Filter DataFrame to return only rows that represent sales exceptions
    (where actual units fall below target_units * threshold_pct / 100).

    Parameters:
        df: Input pandas DataFrame from SQL query execution.
        threshold_pct: Configurable percentage target threshold (e.g. 90.0 means < 90% of target).

    Returns:
        Filtered DataFrame containing only exception rows with added metric columns.
    """
    if df.empty:
        return df

    df_copy = df.copy()

    # Identify target and actual columns in DataFrame
    cols_lower = {c.lower(): c for c in df_copy.columns}

    target_col = None
    actual_col = None

    for col_lower, original_col in cols_lower.items():
        if "target" in col_lower:
            target_col = original_col
        elif "actual" in col_lower:
            actual_col = original_col

    # If both target and actual columns exist in the result DataFrame
    if target_col and actual_col:
        # Calculate achievement percentage and unit deficit
        threshold_factor = float(threshold_pct) / 100.0
        
        # Filter condition: actual < target * threshold_factor
        condition = df_copy[actual_col] < (df_copy[target_col] * threshold_factor)
        flagged_df = df_copy[condition].copy()

        if not flagged_df.empty:
            # Add calculated metric columns for rich UI display
            flagged_df["achievement_pct"] = (
                (flagged_df[actual_col] / flagged_df[target_col]) * 100.0
            ).round(1)

            flagged_df["unit_deficit"] = flagged_df[target_col] - flagged_df[actual_col]

            # Sort by achievement percentage ascending (worst performance first)
            flagged_df = flagged_df.sort_values(by="achievement_pct", ascending=True)

        return flagged_df

    # If query results don't contain both target and actual (e.g., custom aggregations or non-target queries),
    # return the DataFrame as-is.
    return df_copy


if __name__ == "__main__":
    sample_data = pd.DataFrame({
        "region": ["North", "South", "East", "West"],
        "product": ["Chips", "Soda", "Chocolate", "Cookies"],
        "target_units": [1000, 1000, 1000, 1000],
        "actual_units": [950, 850, 700, 1100]
    })

    print("Original Data:\n", sample_data)
    print("\nFlagged Exceptions (< 90% target):\n", flag_exceptions(sample_data, 90.0))
