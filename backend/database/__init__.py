"""
backend/database - Database Layer

This module provides database operations for job data.
"""

from .connection import get_connection, init_database, close_connection
from .operations import (
    save_job, get_jobs, get_job_by_id, delete_job, get_stats, search_jobs, get_most_recent_jobs
)

__all__ = [
    'get_connection',
    'init_database',
    'close_connection',
    'save_job',
    'get_jobs',
    'get_job_by_id',
    'delete_job',
    'get_stats',
    'search_jobs',
    'get_most_recent_jobs',
]
