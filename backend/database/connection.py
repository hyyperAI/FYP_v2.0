"""
backend/database/connection.py

Database connection management using SQLite.
"""

import sqlite3
import threading
from pathlib import Path
from typing import Any, Optional

_db_lock = threading.Lock()


def get_connection() -> sqlite3.Connection:
    """
    Get SQLite connection for current thread.
    Thread-local connections for concurrent workers.

    Returns
    -------
    conn : sqlite3.Connection
        SQLite connection object.
    """
    thread_id = threading.get_ident()

    if not hasattr(get_connection, '_local'):
        get_connection._local = threading.local()

    if not hasattr(get_connection._local, 'conn'):
        db_path = Path('upwork_jobs.db').absolute()
        get_connection._local.conn = sqlite3.connect(str(db_path))
        get_connection._local.conn.row_factory = sqlite3.Row
        get_connection._local.conn.execute('PRAGMA journal_mode=WAL')

    return get_connection._local.conn


def close_connection() -> None:
    """Close the database connection for current thread."""
    if hasattr(get_connection, '_local') and hasattr(get_connection._local, 'conn'):
        get_connection._local.conn.close()
        delattr(get_connection._local, 'conn')


def init_database() -> None:
    """
    Initialize database schema and tables.
    Creates jobs table with all required fields and indexes.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            job_url TEXT UNIQUE NOT NULL,
            time INTEGER,
            skills TEXT,
            type TEXT,
            experience_level TEXT,
            time_estimate TEXT,
            budget TEXT,
            proposals TEXT,
            client_location TEXT,
            client_hire_rate TEXT,
            client_company_size TEXT,
            member_since TEXT,
            client_total_spent TEXT,
            client_hours INTEGER,
            client_jobs_posted INTEGER,
            search_query TEXT,
            scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            task_id TEXT
        )
    ''')

    cursor.execute('CREATE INDEX IF NOT EXISTS idx_jobs_search_query ON jobs(search_query)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_jobs_type ON jobs(type)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_jobs_budget ON jobs(budget)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_jobs_client_location ON jobs(client_location)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_jobs_scraped_at ON jobs(scraped_at)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_jobs_skills ON jobs(skills)')

    # Add task_id column if it doesn't exist (for existing databases)
    cursor.execute("SELECT COUNT(*) FROM pragma_table_info('jobs') WHERE name='task_id'")
    if cursor.fetchone()[0] == 0:
        cursor.execute('ALTER TABLE jobs ADD COLUMN task_id TEXT')
        conn.commit()

    cursor.execute('CREATE INDEX IF NOT EXISTS idx_jobs_task_id ON jobs(task_id)')

    conn.commit()


def create_scrape_tasks_table():
    """Create the scrape_tasks table for task tracking"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS scrape_tasks (
            task_id TEXT PRIMARY KEY,
            query TEXT NOT NULL,
            params TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            job_count INTEGER DEFAULT 0,
            remaining_jobs INTEGER DEFAULT 0,
            error_message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP
        )
    ''')

    cursor.execute('CREATE INDEX IF NOT EXISTS idx_scrape_tasks_status ON scrape_tasks(status)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_scrape_tasks_created_at ON scrape_tasks(created_at)')

    conn.commit()


def create_monitoring_tables():
    """Create tables for monitoring functionality"""
    conn = get_connection()
    cursor = conn.cursor()

    # Create monitoring_sessions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS monitoring_sessions (
            session_id TEXT PRIMARY KEY,
            search_query TEXT NOT NULL,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_scan_at TIMESTAMP,
            jobs_found INTEGER DEFAULT 0,
            status TEXT DEFAULT 'running',
            browser_pid INTEGER,
            webhooks_sent INTEGER DEFAULT 0,
            config TEXT
        )
    ''')

    # Create job_alerts table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS job_alerts (
            alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT,
            job_url TEXT,
            webhook_url TEXT NOT NULL,
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            response_status INTEGER,
            response_body TEXT,
            session_id TEXT
        )
    ''')

    # Create monitoring_stats table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS monitoring_stats (
            stat_date DATE PRIMARY KEY,
            session_id TEXT,
            total_scans INTEGER DEFAULT 0,
            new_jobs_found INTEGER DEFAULT 0,
            webhooks_sent INTEGER DEFAULT 0,
            uptime_minutes INTEGER DEFAULT 0,
            errors_count INTEGER DEFAULT 0
        )
    ''')

    # Create indexes for better performance
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_monitoring_sessions_status ON monitoring_sessions(status)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_monitoring_sessions_started ON monitoring_sessions(started_at)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_job_alerts_session ON job_alerts(session_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_job_alerts_sent_at ON job_alerts(sent_at)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_monitoring_stats_date ON monitoring_stats(stat_date)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_monitoring_stats_session ON monitoring_stats(session_id)')

    conn.commit()


# Initialize all tables
init_database()
create_scrape_tasks_table()
create_monitoring_tables()


__all__ = [
    'get_connection',
    'close_connection',
    'init_database',
    'create_scrape_tasks_table',
    'create_monitoring_tables',
]
