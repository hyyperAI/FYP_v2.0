"""
backend/analysis/data_processing.py

Data loading and processing utilities for job analysis.
"""

import pandas as pd


def read_dataset(path: str) -> pd.DataFrame:
    """Read the data in `path` into a dataframe, assign appropriate dtypes to the columns and drop duplicates."""
    df = pd.read_json(path).convert_dtypes()
    category_columns = ["proposals", "client_location", "type", "experience_level", "time_estimate"]
    integer_columns = ['budget', 'client_jobs_posted', 'client_total_spent']
    float_columns = ['client_hire_rate', 'client_hourly_rate']
    df[category_columns] = df[category_columns].astype('category')
    df[integer_columns] = df[integer_columns].apply(lambda series: pd.to_numeric(series, downcast='unsigned'))
    df[float_columns] = df[float_columns].apply(lambda series: pd.to_numeric(series, downcast='float'))
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df = df[~df.drop(['skills', 'time'], axis=1).duplicated()].reset_index(drop=True)
    return df


def filter_df(df: pd.DataFrame) -> pd.DataFrame:
    """Drop any rows containing NA in "budget" or "proposals" columns and caps the maximum budget to 99 percentile."""
    filtered_df = df.dropna(subset=['budget', 'proposals']).reset_index(drop=True)
    budget_cap = int(filtered_df['budget'].quantile(0.99))
    filtered_df['budget'] = filtered_df['budget'].clip(upper=budget_cap)
    return filtered_df


def print_general_info(df: pd.DataFrame) -> None:
    """Prints general information about the dataframe and some of its columns."""
    print(df['type'].value_counts(), '\n')
    print(df['experience_level'].value_counts(), '\n')
    print(df['client_hourly_rate'].describe(), '\n')
    print(df['time_estimate'].value_counts(), '\n')
    print(df.loc[df['type'] == 'Fixed']['budget'].describe(), '\n')
    print(df.loc[df['type'] == 'Hourly']['budget'].describe())


__all__ = [
    'read_dataset',
    'filter_df',
    'print_general_info',
]
