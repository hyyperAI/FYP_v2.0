"""
backend/scrape - Web Scraping Module

This module provides the core scraping functionality for extracting job listings
from Upwork.com using Selenium WebDriver and BeautifulSoup4.

Classes:
    JobsScraper: Main class for scraping Upwork job listings

Functions:
    split_list_into_chunks: Split a list into chunks for parallel processing
    construct_url: Build search URLs for Upwork job queries
    parse_time: Convert relative time strings to Unix timestamps
    parse_budget: Extract budget information from job postings
    parse_total_spent: Parse client total spent values
    parse_one_job: Extract all details from a single job listing
"""

from .engine import JobsScraper
from .parsers import (
    parse_time,
    parse_budget,
    parse_total_spent,
    parse_one_job
)
from .utils import (
    split_list_into_chunks,
    inhibit_sleep,
    time_print,
    sleep
)

__all__ = [
    # Classes
    'JobsScraper',

    # Parsing functions
    'parse_time',
    'parse_budget',
    'parse_total_spent',
    'parse_one_job',

    # Utility functions
    'split_list_into_chunks',
    'inhibit_sleep',
    'time_print',
    'sleep',
]
