"""
backend/database/operations.py

CRUD operations for job data using SQLite.
"""

import json
from typing import Any, Optional, List, Dict
from .connection import get_connection


def save_job(job_data: dict, task_id: Optional[str] = None) -> int:
    """
    Save a job to the database with upsert (insert or update).

    Parameters
    ----------
    job_data : dict
        Job data to save.
    task_id : Optional[str]
        Task ID to associate with this job.

    Returns
    -------
    job_id : int
        ID of the saved job.

    Raises
    ------
    ValueError
        If required fields are missing.
    """
    if not job_data.get('job_id'):
        raise ValueError("job_id is required")

    conn = get_connection()
    cursor = conn.cursor()

    skills_json = json.dumps(job_data.get('skills', []))

    cursor.execute('''
        INSERT INTO jobs (
            job_id, title, description, job_url, time, skills, type,
            experience_level, time_estimate, budget, proposals,
            client_location, client_hire_rate, client_company_size,
            member_since, client_total_spent, client_hours,
            client_jobs_posted, search_query, task_id, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(job_url) DO UPDATE SET
            job_id = EXCLUDED.job_id,
            title = EXCLUDED.title,
            description = EXCLUDED.description,
            time = EXCLUDED.time,
            skills = EXCLUDED.skills,
            type = EXCLUDED.type,
            experience_level = EXCLUDED.experience_level,
            time_estimate = EXCLUDED.time_estimate,
            budget = EXCLUDED.budget,
            proposals = EXCLUDED.proposals,
            client_location = EXCLUDED.client_location,
            client_hire_rate = EXCLUDED.client_hire_rate,
            client_company_size = EXCLUDED.client_company_size,
            member_since = EXCLUDED.member_since,
            client_total_spent = EXCLUDED.client_total_spent,
            client_hours = EXCLUDED.client_hours,
            client_jobs_posted = EXCLUDED.client_jobs_posted,
            search_query = EXCLUDED.search_query,
            task_id = EXCLUDED.task_id,
            updated_at = CURRENT_TIMESTAMP
    ''', (
        job_data.get('job_id'),
        job_data.get('title', ''),
        job_data.get('description', ''),
        job_data.get('job_url'),
        job_data.get('time'),
        skills_json,
        job_data.get('type'),
        job_data.get('experience_level'),
        job_data.get('time_estimate'),
        job_data.get('budget'),
        job_data.get('proposals'),
        job_data.get('client_location'),
        job_data.get('client_hire_rate'),
        job_data.get('client_company_size'),
        job_data.get('member_since'),
        job_data.get('client_total_spent'),
        job_data.get('client_hours'),
        job_data.get('client_jobs_posted'),
        job_data.get('search_query'),
        task_id,
    ))

    conn.commit()

    # For UPSERT operations, return the job_id from the data since lastrowid doesn't work reliably
    # Return job_id if available, otherwise query for it
    if job_data.get('job_id'):
        return job_data['job_id']
    elif job_data.get('job_url'):
        # Query the database to get the job_id
        cursor.execute('SELECT id FROM jobs WHERE job_url = ?', (job_data.get('job_url'),))
        row = cursor.fetchone()
        return row[0] if row else 0
    else:
        return 0


def create_task(task_id: str, query: str, params: dict) -> None:
    """Create a new scraping task"""
    conn = get_connection()
    conn.execute(
        'INSERT INTO scrape_tasks (task_id, query, params, status) VALUES (?, ?, ?, ?)',
        (task_id, query, json.dumps(params), 'pending')
    )
    conn.commit()


def update_task_status(
    task_id: str,
    status: str,
    job_count: Optional[int] = None,
    remaining_jobs: Optional[int] = None,
    error_message: Optional[str] = None
) -> None:
    """Update task status and progress"""
    conn = get_connection()
    updates = []
    params = []

    if job_count is not None:
        updates.append('job_count = ?')
        params.append(job_count)

    if remaining_jobs is not None:
        updates.append('remaining_jobs = ?')
        params.append(remaining_jobs)

    if error_message:
        updates.append('error_message = ?')
        params.append(error_message)

    if status:
        updates.append('status = ?')
        params.append(status)

    if status in ['completed', 'failed']:
        updates.append('completed_at = CURRENT_TIMESTAMP')

    # Add task_id as the last parameter
    params.append(task_id)

    if updates:
        query = f'UPDATE scrape_tasks SET {", ".join(updates)} WHERE task_id = ?'
        conn.execute(query, params)
        conn.commit()


def get_task_status(task_id: str) -> Optional[dict]:
    """Get task status by task_id"""
    conn = get_connection()
    cursor = conn.execute(
        'SELECT * FROM scrape_tasks WHERE task_id = ?',
        (task_id,)
    )
    row = cursor.fetchone()
    if not row:
        return None

    return dict(row)


def get_jobs_by_task(task_id: str, page: int = 1, per_page: int = 10) -> tuple[list[dict], int]:
    """Get jobs for a specific task with pagination"""
    conn = get_connection()

    # Get total count
    cursor = conn.execute(
        'SELECT COUNT(*) as total FROM jobs WHERE task_id = ?',
        (task_id,)
    )
    total = cursor.fetchone()['total']

    # Get paginated results
    offset = (page - 1) * per_page
    cursor = conn.execute(
        'SELECT * FROM jobs WHERE task_id = ? LIMIT ? OFFSET ?',
        (task_id, per_page, offset)
    )
    rows = cursor.fetchall()

    # Convert to list of dicts
    jobs = []
    for row in rows:
        job_dict = dict(row)
        # Parse JSON fields
        if job_dict.get('skills'):
            try:
                job_dict['skills'] = json.loads(job_dict['skills'])
            except json.JSONDecodeError:
                job_dict['skills'] = []
        jobs.append(job_dict)

    return jobs, total


def get_jobs(filters: Optional[dict] = None) -> list[dict]:
    """
    Retrieve jobs from the database with optional filters.

    Parameters
    ----------
    filters : Optional[dict]
        Filters to apply (e.g., {'type': 'Fixed', 'search_query': 'Python'}).

    Returns
    -------
    jobs : list[dict]
        List of job dictionaries.
    """
    conn = get_connection()
    cursor = conn.cursor()

    query = 'SELECT * FROM jobs WHERE 1=1'
    params = []

    if filters:
        if filters.get('type'):
            query += ' AND type = ?'
            params.append(filters['type'])

        if filters.get('search_query'):
            query += ' AND search_query = ?'
            params.append(filters['search_query'])

        if filters.get('budget'):
            query += ' AND budget = ?'
            params.append(filters['budget'])

        if filters.get('client_location'):
            query += ' AND client_location = ?'
            params.append(filters['client_location'])

        limit = filters.get('limit', 100)
        offset = filters.get('offset', 0)
        query += f' LIMIT {limit} OFFSET {offset}'

    cursor.execute(query, params)
    rows = cursor.fetchall()

    jobs = []
    for row in rows:
        job_dict = dict(row)
        if job_dict.get('skills'):
            try:
                job_dict['skills'] = json.loads(job_dict['skills'])
            except json.JSONDecodeError:
                job_dict['skills'] = []
        jobs.append(job_dict)

    return jobs


def get_job_by_id(job_id: int) -> Optional[dict]:
    """
    Get a single job by database ID.

    Parameters
    ----------
    job_id : int
        Database ID of the job.

    Returns
    -------
    job : Optional[dict]
        Job dictionary or None if not found.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM jobs WHERE id = ?', (job_id,))
    row = cursor.fetchone()

    if row:
        job_dict = dict(row)
        if job_dict.get('skills'):
            try:
                job_dict['skills'] = json.loads(job_dict['skills'])
            except json.JSONDecodeError:
                job_dict['skills'] = []
        return job_dict

    return None


def delete_job(job_id: int) -> bool:
    """
    Delete a job from the database.

    Parameters
    ----------
    job_id : int
        ID of the job to delete.

    Returns
    -------
    success : bool
        True if deletion was successful.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('DELETE FROM jobs WHERE id = ?', (job_id,))
    conn.commit()

    return cursor.rowcount > 0


def get_stats() -> dict:
    """
    Get database statistics.

    Returns
    -------
    stats : dict
        Database statistics including counts and aggregations.
    """
    conn = get_connection()
    cursor = conn.cursor()

    total_jobs = cursor.execute('SELECT COUNT(*) FROM jobs').fetchone()[0]

    jobs_today = cursor.execute(
        "SELECT COUNT(*) FROM jobs WHERE DATE(scraped_at) = DATE('now')"
    ).fetchone()[0]

    by_type = dict(cursor.execute(
        'SELECT type, COUNT(*) FROM jobs WHERE type IS NOT NULL GROUP BY type'
    ).fetchall())

    by_experience = dict(cursor.execute(
        'SELECT experience_level, COUNT(*) FROM jobs WHERE experience_level IS NOT NULL GROUP BY experience_level'
    ).fetchall())

    total_search_queries = cursor.execute(
        'SELECT COUNT(DISTINCT search_query) FROM jobs WHERE search_query IS NOT NULL'
    ).fetchone()[0]

    return {
        'total_jobs': total_jobs,
        'jobs_today': jobs_today,
        'by_type': by_type,
        'by_experience': by_experience,
        'total_search_queries': total_search_queries,
    }


def search_jobs(query: str, filters: Optional[dict] = None) -> list[dict]:
    """
    Search jobs by query string and optional filters.

    Parameters
    ----------
    query : str
        Search query string.
    filters : Optional[dict]
        Additional filters.

    Returns
    -------
    jobs : list[dict]
        List of matching job dictionaries.
    """
    conn = get_connection()
    cursor = conn.cursor()

    sql = 'SELECT * FROM jobs WHERE (title LIKE ? OR description LIKE ? OR skills LIKE ?)'
    params = [f'%{query}%', f'%{query}%', f'%{query}%']

    if filters:
        if filters.get('type'):
            sql += ' AND type = ?'
            params.append(filters['type'])

        if filters.get('experience_level'):
            sql += ' AND experience_level = ?'
            params.append(filters['experience_level'])

    sql += ' LIMIT 50'
    cursor.execute(sql, params)
    rows = cursor.fetchall()

    jobs = []
    for row in rows:
        job_dict = dict(row)
        if job_dict.get('skills'):
            try:
                job_dict['skills'] = json.loads(job_dict['skills'])
            except json.JSONDecodeError:
                job_dict['skills'] = []
        jobs.append(job_dict)

    return jobs


def get_most_recent_jobs(query: Optional[str] = None, limit: int = 5) -> list[dict]:
    """
    Retrieve the most recent jobs from the database.

    Parameters
    ----------
    query : Optional[str]
        Optional search query to filter jobs.
    limit : int
        Maximum number of jobs to return (default: 5).

    Returns
    -------
    jobs : list[dict]
        List of job dictionaries sorted by scraped_at DESC.
    """
    conn = get_connection()
    cursor = conn.cursor()

    sql = 'SELECT * FROM jobs'
    params = []

    # Add optional WHERE clause for query
    if query:
        sql += ' WHERE (title LIKE ? OR description LIKE ? OR search_query LIKE ? OR skills LIKE ?)'
        search_term = f'%{query}%'
        params.extend([search_term, search_term, search_term, search_term])

    # Add ORDER BY and LIMIT
    sql += ' ORDER BY scraped_at DESC LIMIT ?'
    params.append(limit)

    cursor.execute(sql, params)
    rows = cursor.fetchall()

    jobs = []
    for row in rows:
        job_dict = dict(row)
        # Parse JSON fields
        if job_dict.get('skills'):
            try:
                job_dict['skills'] = json.loads(job_dict['skills'])
            except (json.JSONDecodeError, TypeError):
                job_dict['skills'] = []
        jobs.append(job_dict)

    return jobs


# =============================================================================
# MONITORING-SPECIFIC OPERATIONS
# =============================================================================

def create_monitoring_session(session_id: str, search_query: str, config: dict) -> None:
    """
    Create a new monitoring session record.

    Parameters
    ----------
    session_id : str
        Unique session identifier (UUID).
    search_query : str
        The search query to monitor.
    config : dict
        Configuration dictionary for the session.
    """
    conn = get_connection()
    conn.execute(
        '''INSERT INTO monitoring_sessions
           (session_id, search_query, status, config)
           VALUES (?, ?, 'running', ?)''',
        (session_id, search_query, json.dumps(config))
    )
    conn.commit()


def update_monitoring_session(
    session_id: str,
    status: Optional[str] = None,
    jobs_found: Optional[int] = None,
    webhooks_sent: Optional[int] = None,
    browser_pid: Optional[int] = None,
    last_scan_at: Optional[str] = None
) -> None:
    """
    Update monitoring session status and statistics.

    Parameters
    ----------
    session_id : str
        Session identifier.
    status : Optional[str]
        New status (running, stopped, error).
    jobs_found : Optional[int]
        Total jobs found.
    webhooks_sent : Optional[int]
        Total webhooks sent.
    browser_pid : Optional[int]
        Browser process ID.
    last_scan_at : Optional[str]
        Timestamp of last scan.
    """
    conn = get_connection()
    updates = []
    params = []

    if status is not None:
        updates.append('status = ?')
        params.append(status)

    if jobs_found is not None:
        updates.append('jobs_found = ?')
        params.append(jobs_found)

    if webhooks_sent is not None:
        updates.append('webhooks_sent = ?')
        params.append(webhooks_sent)

    if browser_pid is not None:
        updates.append('browser_pid = ?')
        params.append(browser_pid)

    if last_scan_at is not None:
        updates.append('last_scan_at = ?')
        params.append(last_scan_at)

    if updates:
        params.append(session_id)
        query = f'UPDATE monitoring_sessions SET {", ".join(updates)} WHERE session_id = ?'
        conn.execute(query, params)
        conn.commit()


def log_webhook_alert(
    job_id: Optional[str],
    webhook_url: str,
    response_status: Optional[int] = None,
    response_body: Optional[str] = None,
    session_id: Optional[str] = None,
    job_url: Optional[str] = None
) -> None:
    """
    Record a webhook delivery attempt.

    Parameters
    ----------
    job_id : Optional[str]
        Job identifier (numeric ID).
    webhook_url : str
        URL that was called.
    response_status : Optional[int]
        HTTP response status code.
    response_body : Optional[str]
        Response body content.
    session_id : Optional[str]
        Session identifier.
    job_url : Optional[str]
        Job URL (for duplicate detection).
    """
    conn = get_connection()
    conn.execute(
        '''INSERT INTO job_alerts
           (job_id, job_url, webhook_url, response_status, response_body, session_id)
           VALUES (?, ?, ?, ?, ?, ?)''',
        (job_id, job_url, webhook_url, response_status, response_body, session_id)
    )
    conn.commit()


def record_monitoring_stats(
    session_id: str,
    stat_date: str,
    total_scans: int = 0,
    new_jobs_found: int = 0,
    webhooks_sent: int = 0,
    uptime_minutes: int = 0,
    errors_count: int = 0
) -> None:
    """
    Record daily monitoring statistics.

    Parameters
    ----------
    session_id : str
        Session identifier.
    stat_date : str
        Date in YYYY-MM-DD format.
    total_scans : int
        Total scans performed.
    new_jobs_found : int
        New jobs found.
    webhooks_sent : int
        Webhooks sent.
    uptime_minutes : int
        Uptime in minutes.
    errors_count : int
        Number of errors.
    """
    conn = get_connection()
    conn.execute(
        '''INSERT OR REPLACE INTO monitoring_stats
           (stat_date, session_id, total_scans, new_jobs_found,
            webhooks_sent, uptime_minutes, errors_count)
           VALUES (?, ?, ?, ?, ?, ?, ?)''',
        (stat_date, session_id, total_scans, new_jobs_found,
         webhooks_sent, uptime_minutes, errors_count)
    )
    conn.commit()


def get_monitoring_status(session_id: str) -> Optional[dict]:
    """
    Get current monitoring session information.

    Parameters
    ----------
    session_id : str
        Session identifier.

    Returns
    -------
    status : Optional[dict]
        Session status dictionary or None if not found.
    """
    conn = get_connection()
    cursor = conn.execute(
        'SELECT * FROM monitoring_sessions WHERE session_id = ?',
        (session_id,)
    )
    row = cursor.fetchone()
    return dict(row) if row else None


def get_recent_alerts(limit: int = 100) -> list[dict]:
    """
    Get recent webhook alerts.

    Parameters
    ----------
    limit : int
        Maximum number of alerts to return.

    Returns
    -------
    alerts : list[dict]
        List of alert dictionaries.
    """
    conn = get_connection()
    cursor = conn.execute(
        'SELECT * FROM job_alerts ORDER BY sent_at DESC LIMIT ?',
        (limit,)
    )
    rows = cursor.fetchall()
    return [dict(row) for row in rows]


__all__ = [
    'save_job',
    'get_jobs',
    'get_job_by_id',
    'delete_job',
    'get_stats',
    'search_jobs',
    'create_task',
    'update_task_status',
    'get_task_status',
    'get_jobs_by_task',
    'get_most_recent_jobs',
    # Monitoring operations
    'create_monitoring_session',
    'update_monitoring_session',
    'log_webhook_alert',
    'record_monitoring_stats',
    'get_monitoring_status',
    'get_recent_alerts',
]
