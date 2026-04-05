"""
backend/analysis - Data Analysis Module

This module provides statistical analysis and visualization capabilities
for scraped Upwork job data.

Functions:
    perform_analysis: Run complete analysis workflow
    read_dataset: Load job data from JSON file
    filter_df: Clean and filter job data
    plot_budget_ranges: Visualize budget distributions
    plot_job_post_frequency: Analyze posting patterns
    plot_highest_paying_countries: Show geographic pay trends
    plot_most_common_skills: Display skill demand
    plot_skills_and_budget: Analyze skill-pay correlations
    plot_skills_and_proposals: Analyze skill-competition relationships
"""

from .engine import perform_analysis
from .data_processing import (
    read_dataset,
    filter_df,
    print_general_info
)
from .statistics import (
    get_most_common_skills,
    transform_to_binary_skills,
    get_skills_correlated_with_budget,
    get_skills_of_interest,
    interest_df
)
from .visualization import (
    plot_budget_ranges,
    plot_job_post_frequency,
    plot_highest_paying_countries,
    plot_most_common_skills,
    plot_skills_and_budget,
    plot_skills_and_proposals,
    save_all_figures
)

__all__ = [
    # Main function
    'perform_analysis',

    # Data processing
    'read_dataset',
    'filter_df',
    'print_general_info',

    # Statistics
    'get_most_common_skills',
    'transform_to_binary_skills',
    'get_skills_correlated_with_budget',
    'get_skills_of_interest',
    'interest_df',

    # Visualization
    'plot_budget_ranges',
    'plot_job_post_frequency',
    'plot_highest_paying_countries',
    'plot_most_common_skills',
    'plot_skills_and_budget',
    'plot_skills_and_proposals',
    'save_all_figures',
]
