"""
backend/analysis/statistics.py

Statistical analysis functions for job data.
"""

from typing import Any
from typing import Callable

import pandas as pd
from sklearn.preprocessing import MultiLabelBinarizer
from scipy.stats import spearmanr


def _process_plot(plot_function: Callable, fig_num: int, tick_rotation: int | None = None) -> Any:
    """
    Assign a specific figure to each plot that can be retrieved again by other functions in this module and set the
    layout to tight layout to automatically adjust spacing.
    """
    import matplotlib.pyplot as plt
    import seaborn as sns

    fig = plt.figure(fig_num)
    if isinstance(plot_function(), sns.FacetGrid):  # xticks doesn't work with FacetGrid.
        for ax in fig.axes:
            ax.tick_params("x", labelrotation=tick_rotation)
    else:
        plt.xticks(rotation=tick_rotation)
    fig.tight_layout()
    return fig


def _fixed_boxplot(x: Any, y: Any, *args: Any, label: Any = None, **kwargs: dict[str, Any]) -> None:
    """Earlier versions of matplotlib and seaborn had an error when mapping `boxplot` to `FacetGrid`, this is a fix."""
    import seaborn as sns
    try:  # For newer versions.
        sns.boxplot(x=x, y=y, *args, **kwargs, label=label)
    except TypeError:  # For older versions.
        sns.boxplot(x=x, y=y, *args, **kwargs, labels=[label])


def get_most_common_skills(df: pd.DataFrame, n: int | None = None) -> dict[str, int]:
    """Return a dict containing the `n` most common skills ordered from most to least frequent and their count."""
    skills_counter: dict[str, int] = {}
    for skills_set in df['skills']:
        for skill in skills_set:
            skills_counter[skill] = skills_counter.get(skill, 0) + 1
    if not n:
        n = len(skills_counter) + 1  # To get all the values.
    return dict(sorted(skills_counter.items(), key=lambda x: x[1], reverse=True)[:n])


def transform_to_binary_skills(df: pd.DataFrame) -> pd.DataFrame:
    """Find all the unique skills in df and add each skill's presence as its own column in a copy of the original df."""
    from .data_processing import filter_df
    if df[['budget', 'proposals']].isna().any().any():  # If unfiltered df is passed filter it.
        df = filter_df(df)
    mlb = MultiLabelBinarizer()
    skills_transformed = mlb.fit_transform(df['skills'])
    skills_df = pd.DataFrame(skills_transformed, columns=mlb.classes_)
    df_skills_binary = pd.concat([df, skills_df], axis=1)
    return df_skills_binary


def get_skills_correlated_with_budget(skills_df: pd.DataFrame, corr_value: float = 0.05) -> list[str]:
    """
    Calculates the Spearman correlation coefficient between each skill in the dataframe and budget.
    The chosen skills are the ones that resulted in a p value <= 0.05 and correlation coefficient >= `corr_value`.

    .. note::
        The `skills_df` should be the transformed dataframe that contains each skill as a column. This can be obtained
        using the `transform_to_binary_skills` function.
    """
    blacklist_columns = [
        'title', 'description', 'time', 'skills', 'type', 'experience_level', 'time_estimate', 'budget', 'proposals',
        'client_location', 'client_jobs_posted', 'client_hire_rate', 'client_hourly_rate', 'client_total_spent']
    high_budget_corr_skills = []
    for column_name in skills_df.columns:
        skill_column = skills_df[column_name]
        if skill_column.name not in blacklist_columns:
            corr, p_value = spearmanr(skill_column, skills_df['budget'])
            if p_value <= 0.05 and corr >= corr_value:
                high_budget_corr_skills.append(column_name)
    return high_budget_corr_skills


def get_skills_of_interest(
        influence_budget_skills: list | None = None,
        common_skills: list | None = None,
        skills_df: pd.DataFrame | None = None
) -> list[str]:
    """
    skills of interest are defined as the intersection between skills that occur more than 15 times (common skills) and
    skills that influence the budget positively (their presence correlate with increased budget) more than 5% unless
    `influence_budget_skills` and `common_skills` arguments are passed.
    `skills_df` only needs to be passed if either `influence_budget_skills` or `common_skill` are None.
    """
    if not influence_budget_skills:
        influence_budget_skills = get_skills_correlated_with_budget(skills_df)
    if not common_skills:
        common_skills = [skill for skill, count in get_most_common_skills(skills_df).items() if count >= 15]
    return list(set(common_skills).intersection(influence_budget_skills))


def interest_df(skills_df: pd.DataFrame, skills_of_interest: list | None = None) -> pd.DataFrame:
    """Create a dataframe that only contains skill, budget and proposals columns and each row contains one skill."""
    if not skills_of_interest:
        skills_of_interest = get_skills_of_interest(skills_df=skills_df)
    if not skills_of_interest:
        # If the above call resulted in an empty list, it means there isn't enough data to find any relationship.
        # Return an empty dataframe instead of crashing
        return pd.DataFrame(columns=['budget', 'proposals', 'skill'])
    df_melted = skills_df.melt(
        id_vars=['budget', 'proposals'], value_vars=skills_of_interest, var_name='skill', value_name='presence')
    # Filter only the rows where the skill is present
    df_melted = df_melted[df_melted['presence'] == 1].drop('presence', axis=1)
    return df_melted


__all__ = [
    'get_most_common_skills',
    'transform_to_binary_skills',
    'get_skills_correlated_with_budget',
    'get_skills_of_interest',
    'interest_df',
    '_process_plot',
    '_fixed_boxplot',
]
