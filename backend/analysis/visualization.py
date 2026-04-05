"""
backend/analysis/visualization.py

Plotting and visualization functions for job analysis.
"""

from datetime import timedelta
from typing import Any
from typing import Callable
import os
import time

import pandas as pd
import seaborn as sns
from matplotlib import pyplot as plt

from .statistics import _process_plot, _fixed_boxplot


def plot_budget_ranges(df: pd.DataFrame) -> plt.Figure:
    """Cuts the dataframe "budget" column into 16 ranges/groups and plots their frequency."""
    budget_groups = [
        '<10$', '10-20$', '20-30$', '30-40$', '40-50$', '50-100$', '100-200$', '200-300$', '300-400$', '400-500$',
        '500-1000$', '1000-5000$', '5000-10000$', "10000-50000$", ">50000$"]
    budget_bins = [0, 10, 20, 30, 40, 50, 100, 200, 300, 400, 500, 1000, 5000, 10000, 50_000, int(1e9)]
    budget_ranges = pd.cut(df['budget'], bins=budget_bins, labels=budget_groups)
    return _process_plot(
        lambda: sns.countplot(x=budget_ranges, order=budget_groups).set(
            title="Budget ranges count", xlabel="Budget Range", ylabel="Count",
            yticks=range(0, budget_ranges.value_counts().max(), 20)),
        1, 45)


def plot_job_post_frequency(df: pd.DataFrame) -> plt.Figure:
    """Plots the frequency of new job posts on each day of the week"""
    df_one_week = df[df['time'] >= (df['time'].max() - timedelta(days=7))].copy()
    df_one_week['day'] = df_one_week['time'].dt.day_name()
    return _process_plot(lambda: sns.countplot(
        df_one_week, x='day', order=['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']), 2)


def plot_highest_paying_countries(df: pd.DataFrame, n: int = 15) -> plt.Figure:
    """Plots the `n` highest paying countries."""
    counts = df.dropna(subset=['budget'])['client_location'].value_counts()
    no_four_trick_ponies = df[df['client_location'].isin(counts.index[counts > 4])]
    top_countries = (
        no_four_trick_ponies
        .groupby("client_location", observed=False)
        .budget
        .mean()
        .reset_index()
        .sort_values('budget', ascending=False)
        .dropna(subset=['budget'])
        .head(n)
    )
    top_countries['client_location'] = top_countries['client_location'].astype('string')
    if not len(top_countries):
        top_countries = pd.DataFrame({'client_location': 'NA', 'budget': 0}, index=[0])
    # Convert category dtype to string because seaborn will display all the categories even if they are not
    # present in chosen dataframe, this is probably a bug with seaborn.
    return _process_plot(lambda: sns.barplot(top_countries, x='client_location', y='budget'), 3, 90)


def plot_most_common_skills(df: pd.DataFrame, n: int | None = 20) -> plt.Figure:
    """Plots the most common skills and how many times they occurred."""
    from .statistics import get_most_common_skills
    # Earlier versions of seaborn couldn't directly take dicts as input. This is a fix, so it can work on Python 3.7.
    skill_counts_df = pd.DataFrame(get_most_common_skills(df, n), index=[0])
    return _process_plot(lambda: sns.barplot(
        skill_counts_df, orient='h').set(title="Skills count", xlabel="Skill", ylabel="Count"), 4)


def plot_skills_and_budget(
        skills_df: pd.DataFrame, skills_of_interest: list | None = None) -> tuple[plt.Figure, plt.Figure]:
    """Plots the chosen skills (`skills_of_interest`) and the budget associated with the skills."""
    from .statistics import interest_df
    df_melted = interest_df(skills_df, skills_of_interest)
    # Check if we have data to plot
    if df_melted.empty:
        # Return placeholder figures
        fig1, ax1 = plt.subplots(figsize=(6, 4))
        ax1.text(0.5, 0.5, 'No skills data available', ha='center', va='center', fontsize=12)
        ax1.axis('off')
        plt.figure(5)

        fig2, ax2 = plt.subplots(figsize=(6, 4))
        ax2.text(0.5, 0.5, 'No skills data available', ha='center', va='center', fontsize=12)
        ax2.axis('off')
        plt.figure(6)
        return fig1, fig2

    f1 = _process_plot(lambda: sns.boxplot(df_melted, x='skill', y='budget', order=skills_of_interest).set(
        title="Distribution of Budgets by Skill Presence"), 5, 90)

    g = sns.FacetGrid(
        df_melted, col="proposals", hue='proposals', col_wrap=2, height=8, sharex=False, sharey=False,
        col_order=['Less than 5', '5 to 10', '10 to 15', '15 to 20', '20 to 50', '50+'])
    f2 = _process_plot(lambda: g.map(_fixed_boxplot, "skill", "budget", order=skills_of_interest), 6, 90)
    f2.suptitle('Distribution of Budgets by Skill Presence and Number of Proposals')
    return f1, f2


def plot_skills_and_proposals(skills_df: pd.DataFrame, skills_of_interest: list | None = None) -> plt.Figure:
    """Plot a heatmap of the skills and number of proposals to show if there is a relation between them."""
    from .statistics import interest_df
    df_melted = interest_df(skills_df, skills_of_interest)
    # Check if we have data to plot
    if df_melted.empty:
        # Return a placeholder figure
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.text(0.5, 0.5, 'No skills data available', ha='center', va='center', fontsize=12)
        ax.axis('off')
        plt.figure(7)
        return fig
    contingency_table = pd.crosstab(df_melted['proposals'], df_melted['skill'], normalize='columns').reindex(
        ['Less than 5', '5 to 10', '10 to 15', '15 to 20', '20 to 50', '50+']).T
    return _process_plot(lambda: sns.heatmap(contingency_table, annot=True, fmt='.2g'), 7)


def save_all_figures(directory: str, randomize_name: bool = True) -> None:
    """Save *only* all the figures created by this module in `directory`."""
    fig_num_mapping = {
        1: "budget_ranges", 2: "post_frequency", 3: "highest_paying_countries", 4: "common_skills",
        5: "skills_budget", 6: "skills_budget_grid", 7: "skills_proposals"}
    if not os.path.isdir(directory):
        os.mkdir(directory)
    print(f"Saving to {directory}")
    for fig_num in plt.get_fignums():
        if fig_num in range(1, 8):
            fig_name = fig_num_mapping[fig_num] + "_plot"
            if randomize_name:
                fig_name += f"_{int(time.time())}"
            plt.figure(fig_num).savefig(os.path.join(directory, f"{fig_name}.png"))


__all__ = [
    'plot_budget_ranges',
    'plot_job_post_frequency',
    'plot_highest_paying_countries',
    'plot_most_common_skills',
    'plot_skills_and_budget',
    'plot_skills_and_proposals',
    'save_all_figures',
]
