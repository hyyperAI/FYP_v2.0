"""
backend/analysis/engine.py

Main analysis engine for performing comprehensive analysis on scraped job data.
"""

import argparse

from matplotlib import pyplot as plt
import seaborn as sns

from .data_processing import (
    read_dataset,
    print_general_info
)
from .visualization import (
    plot_budget_ranges,
    plot_highest_paying_countries,
    plot_job_post_frequency,
    plot_most_common_skills,
    plot_skills_and_budget,
    plot_skills_and_proposals,
    save_all_figures
)
from .statistics import transform_to_binary_skills


def perform_analysis(dataset_path: str, save_plots_dir: str | None = None, show_plots: bool = True) -> None:
    """
    Perform all the data analysis techniques available in this module and plot the result.

    Parameters
    ----------
    dataset_path: str
        The path to the json file containing the scraped data.
    save_plots_dir: str, optional
        Where to save the plots after creating them. If None or an empty string, the plots won't be saved.
    show_plots: bool, optional
        Whether to show the plots after creating them. Default is True
    """
    df = read_dataset(dataset_path)
    print_general_info(df)
    plot_budget_ranges(df)
    plot_highest_paying_countries(df)
    plot_job_post_frequency(df)
    plot_most_common_skills(df)
    skills_df = transform_to_binary_skills(df)
    plot_skills_and_budget(skills_df)
    plot_skills_and_proposals(skills_df)
    if save_plots_dir:
        save_all_figures(save_plots_dir)
    if show_plots:
        plt.show()


def analysis_cli_entry_point() -> None:
    """CLI entry point for analysis module."""
    sns.set(style='whitegrid', palette="deep", font_scale=1.1, rc={"figure.figsize": [10, 6]})
    parser = argparse.ArgumentParser(
        description="Perform data analysis on the data collected by scraping upwork and plot the data.")
    parser.add_argument(
        "dataset_path", type=str, help="The path to the scraped data.")
    parser.add_argument(
        "-o", "--save-dir", type=str, help="The directory to save the plots to. If not passed, don't save the plots.")
    parser.add_argument(
        "-s", "--show", action="store_true", help="Whether to show the plots. Off by default.")
    args = parser.parse_args()
    scraped_data_path = args.dataset_path
    save_directory = args.save_dir
    show = args.show
    perform_analysis(scraped_data_path, save_directory, show)


if __name__ == '__main__':
    analysis_cli_entry_point()
    # Direct usage example
    # perform_analysis("saved_jobs.json", "save_dir/", True)
