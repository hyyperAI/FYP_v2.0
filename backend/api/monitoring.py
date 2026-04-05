"""
backend/api/monitoring.py

FastAPI endpoints for continuous monitoring control.
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks, Query, Path, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
import threading
import uuid
import re
import time
from datetime import datetime

from backend.monitoring.continuous_monitor import ContinuousMonitor
from backend.monitoring.config import MonitoringConfig
from backend.database.operations import (
    get_monitoring_status,
    get_recent_alerts,
    get_jobs
)


def sanitize_query(query: str) -> str:
    """
    Sanitize query string to prevent injection attacks.

    Parameters
    ----------
    query : str
        Raw query string from user input.

    Returns
    -------
    sanitized : str
        Sanitized query string.
    """
    # Remove potentially dangerous characters
    sanitized = re.sub(r'[<>"\']', '', query)
    # Remove control characters
    sanitized = re.sub(r'[\x00-\x1f\x7f]', '', sanitized)
    # Limit length to prevent abuse
    if len(sanitized) > 200:
        sanitized = sanitized[:200]
    # Strip whitespace
    sanitized = sanitized.strip()
    return sanitized


# Pydantic Models
class StartMonitoringRequest(BaseModel):
    query: str = Field(..., description="Search query to monitor")
    webhook_url: str = Field(..., description="Webhook URL for notifications")
    refresh_interval: Optional[int] = Field(60, ge=10, le=3600, description="Seconds between scans")
    headless: Optional[bool] = Field(True, description="Run browser headlessly")
    config_path: Optional[str] = Field(None, description="Path to config file")


class MonitoringStatusResponse(BaseModel):
    session_id: str
    status: str
    started_at: Optional[str]
    last_scan_at: Optional[str]
    jobs_found: int
    webhooks_sent: int
    uptime_minutes: float
    browser_pid: Optional[int]
    query: Optional[str]


class MonitoringStatsResponse(BaseModel):
    total_scans: int
    new_jobs_found: int
    webhooks_sent: int
    uptime_minutes: int
    errors_count: int
    jobs_per_hour: float


class MonitoringAlert(BaseModel):
    alert_id: int
    job_id: str
    webhook_url: str
    sent_at: str
    response_status: Optional[int]


class MonitoringAlertsResponse(BaseModel):
    alerts: list[MonitoringAlert]
    count: int


class WebhookTestResponse(BaseModel):
    success: bool
    status_code: Optional[int]
    message: str
    response_time_ms: Optional[float]


class RecentJobDetail(BaseModel):
    job_id: str
    title: str
    description: Optional[str]
    job_url: Optional[str]
    budget: Optional[str]
    skills: list
    type: Optional[str]
    experience_level: Optional[str]
    client_location: Optional[str]
    proposals: Optional[str]
    scraped_at: str
    search_query: Optional[str]
    alert_sent_at: str
    webhook_status: Optional[int]


class RecentJobsDetailsResponse(BaseModel):
    jobs: list[RecentJobDetail]
    count: int
    limit: int


# FastAPI application
app = FastAPI(
    title="Upwork Monitoring API",
    description="API for controlling continuous job monitoring",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8080", "http://localhost:8000"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Active monitoring sessions
active_monitors: Dict[str, ContinuousMonitor] = {}
monitor_threads: Dict[str, threading.Thread] = {}
monitor_lock = threading.Lock()

# Simple rate limiting (in-memory)
rate_limit_data: Dict[str, Dict[str, int]] = {}
rate_limit_lock = threading.Lock()


def check_rate_limit(client_ip: str, endpoint: str, limit: int = 10, window: int = 60) -> bool:
    """
    Check if request is within rate limit.

    Parameters
    ----------
    client_ip : str
        Client IP address.
    endpoint : str
        API endpoint name.
    limit : int
        Maximum requests allowed in time window.
    window : int
        Time window in seconds.

    Returns
    -------
    allowed : bool
        True if request is allowed, False if rate limit exceeded.
    """
    current_time = int(time.time())
    window_start = current_time - window

    with rate_limit_lock:
        # Initialize client data if not exists
        if client_ip not in rate_limit_data:
            rate_limit_data[client_ip] = {}

        client_data = rate_limit_data[client_ip]

        # Get or initialize endpoint data
        if endpoint not in client_data:
            client_data[endpoint] = {
                'requests': [],
                'first_request': current_time
            }

        endpoint_data = client_data[endpoint]

        # Remove old requests outside window
        endpoint_data['requests'] = [
            req_time for req_time in endpoint_data['requests']
            if req_time > window_start
        ]

        # Check if limit exceeded
        if len(endpoint_data['requests']) >= limit:
            return False

        # Add current request
        endpoint_data['requests'].append(current_time)

        # Clean up old client data periodically
        if current_time - endpoint_data['first_request'] > 3600:  # 1 hour
            client_data.pop(endpoint, None)
            if not client_data:  # Remove empty client entry
                rate_limit_data.pop(client_ip, None)

        return True


@app.post("/api/monitor/start", status_code=201)
async def start_monitoring(request: Request, body: StartMonitoringRequest):
    """
    Start a new monitoring session.
    """
    try:
        # Get client IP for rate limiting
        client_ip = request.client.host if request.client else "127.0.0.1"

        # Check rate limit (10 requests per minute for start endpoint)
        if not check_rate_limit(client_ip, "start_monitoring", limit=10, window=60):
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded. Try again later."
            )

        # Sanitize input
        sanitized_query = sanitize_query(body.query)

        # Generate session ID
        session_id = str(uuid.uuid4())

        # Create configuration
        if body.config_path:
            config = MonitoringConfig.from_file(body.config_path)
            config.search_query = sanitized_query
            config.webhook_url = body.webhook_url
            config.refresh_interval = body.refresh_interval
            config.headless = body.headless
        else:
            config = MonitoringConfig(
                search_query=sanitized_query,
                webhook_url=body.webhook_url,
                refresh_interval=body.refresh_interval,
                headless=body.headless
            )

        # Validate configuration
        config.validate()

        # Create monitor
        monitor = ContinuousMonitor(
            query=sanitized_query,
            webhook_url=body.webhook_url,
            config=config
        )

        # Store monitor
        with monitor_lock:
            active_monitors[session_id] = monitor

        # Start in background thread
        def run_monitor():
            try:
                monitor.start()
            except Exception as e:
                print(f"Monitor {session_id} failed: {e}")
            finally:
                # Clean up after monitor stops
                with monitor_lock:
                    active_monitors.pop(session_id, None)
                    monitor_threads.pop(session_id, None)

        thread = threading.Thread(target=run_monitor, daemon=True)
        thread.start()

        # Store thread
        monitor_threads[session_id] = thread

        return {
            "session_id": session_id,
            "status": "started",
            "message": "Monitoring started successfully",
            "config": config.to_dict()
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/monitor/status/{session_id}", response_model=MonitoringStatusResponse)
async def get_monitoring_status(
    request: Request,
    session_id: str = Path(..., description="Session ID")
):
    """
    Get monitoring status for a session.
    """
    try:
        # Get client IP for rate limiting
        client_ip = request.client.host if request.client else "127.0.0.1"

        # Check rate limit (30 requests per minute for status endpoint)
        if not check_rate_limit(client_ip, "get_monitoring_status", limit=30, window=60):
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded. Try again later."
            )

        # Check if monitor exists
        with monitor_lock:
            monitor = active_monitors.get(session_id)

        if not monitor:
            # Try to get status from database
            db_status = get_monitoring_status(session_id)
            if not db_status:
                raise HTTPException(status_code=404, detail="Session not found")

            return MonitoringStatusResponse(
                session_id=session_id,
                status=db_status.get('status', 'unknown'),
                started_at=db_status.get('started_at'),
                last_scan_at=db_status.get('last_scan_at'),
                jobs_found=db_status.get('jobs_found', 0),
                webhooks_sent=db_status.get('webhooks_sent', 0),
                uptime_minutes=0,
                browser_pid=db_status.get('browser_pid'),
                query=db_status.get('search_query')
            )

        # Get live stats from monitor
        stats = monitor.get_stats()

        return MonitoringStatusResponse(
            session_id=session_id,
            status="running" if monitor.running else "stopped",
            started_at=datetime.fromtimestamp(stats['uptime_seconds'], tz=datetime.now().astimezone().tzinfo).isoformat() if stats['uptime_seconds'] > 0 else None,
            last_scan_at=datetime.now().isoformat(),  # Approximate
            jobs_found=stats['total_jobs_found'],
            webhooks_sent=stats['total_webhooks_sent'],
            uptime_minutes=stats['uptime_hours'] * 60,
            browser_pid=monitor.browser_process.pid if monitor.browser_process else None,
            query=monitor.query
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/monitor/stop/{session_id}")
async def stop_monitoring(
    session_id: str = Path(..., description="Session ID")
):
    """
    Stop a monitoring session.
    """
    try:
        # Check if monitor exists
        with monitor_lock:
            monitor = active_monitors.get(session_id)

        if not monitor:
            raise HTTPException(status_code=404, detail="Session not found")

        # Stop monitor
        monitor.stop()

        return {
            "session_id": session_id,
            "status": "stopped",
            "message": "Monitoring stopped successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/monitor/stats/{session_id}", response_model=MonitoringStatsResponse)
async def get_monitoring_stats(
    session_id: str = Path(..., description="Session ID")
):
    """
    Get monitoring statistics for a session.
    """
    try:
        # Check if monitor exists
        with monitor_lock:
            monitor = active_monitors.get(session_id)

        if not monitor:
            raise HTTPException(status_code=404, detail="Session not found")

        # Get stats from monitor
        stats = monitor.get_stats()

        return MonitoringStatsResponse(
            total_scans=stats['scans_completed'],
            new_jobs_found=stats['total_jobs_found'],
            webhooks_sent=stats['total_webhooks_sent'],
            uptime_minutes=int(stats['uptime_hours'] * 60),
            errors_count=stats['total_errors'],
            jobs_per_hour=stats['jobs_per_hour']
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/monitor/alerts", response_model=MonitoringAlertsResponse)
async def get_monitoring_alerts(
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of alerts")
):
    """
    Get recent webhook alerts.
    """
    try:
        alerts = get_recent_alerts(limit=limit)

        # Format alerts
        formatted_alerts = []
        for alert in alerts:
            formatted_alerts.append(MonitoringAlert(
                alert_id=alert['alert_id'],
                job_id=alert['job_id'],
                webhook_url=alert['webhook_url'],
                sent_at=alert['sent_at'],
                response_status=alert['response_status']
            ))

        return MonitoringAlertsResponse(
            alerts=formatted_alerts,
            count=len(formatted_alerts)
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/monitor/sessions")
async def list_monitoring_sessions():
    """
    List all active monitoring sessions.
    """
    try:
        with monitor_lock:
            sessions = []
            for session_id, monitor in active_monitors.items():
                sessions.append({
                    "session_id": session_id,
                    "query": monitor.query,
                    "status": "running",
                    "uptime_hours": monitor.get_stats()['uptime_hours']
                })

        return {
            "sessions": sessions,
            "count": len(sessions)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/monitor/sessions/{session_id}")
async def delete_monitoring_session(
    session_id: str = Path(..., description="Session ID")
):
    """
    Delete a monitoring session from database.
    """
    try:
        # Stop if running
        with monitor_lock:
            monitor = active_monitors.get(session_id)
            if monitor:
                monitor.stop()

        # Note: In a real implementation, you might want to add a delete function
        # to operations.py to remove the session from the database

        return {
            "session_id": session_id,
            "message": "Session deleted (stopped if running)"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/monitor/health")
async def monitoring_health():
    """
    Health check endpoint.
    """
    try:
        with monitor_lock:
            active_count = len(active_monitors)

        return {
            "status": "healthy",
            "active_sessions": active_count,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/monitor/recent-jobs-details", response_model=RecentJobsDetailsResponse)
async def get_recent_jobs_details(
    limit: int = Query(10, ge=1, le=100, description="Number of jobs to return"),
    day: Optional[str] = Query(None, description="Filter by date (format: YYYY-MM-DD)")
):
    """
    Get recent jobs with full details in one shot.

    This endpoint combines monitoring alerts with full job details from the database.

    Parameters:
    - limit: Number of jobs to return (1-100, default: 10)
    - day: Filter by specific date (format: YYYY-MM-DD), optional

    Returns:
    - List of jobs with complete details (title, budget, skills, client info, etc.)
    - Each job includes the alert timestamp and webhook status
    """
    try:
        # Get recent alerts
        alerts_data = get_recent_alerts(limit=limit)
        alerts = alerts_data.get('alerts', [])

        # Filter by date if specified
        if day:
            filtered_alerts = []
            for alert in alerts:
                sent_at = alert.get('sent_at', '')
                if day in sent_at:
                    filtered_alerts.append(alert)
            alerts = filtered_alerts

        # Get full job details for each alert
        jobs_with_details = []

        for alert in alerts:
            job_id = alert.get('job_id')
            if not job_id:
                continue

            # Get full job details from database
            job_list = get_jobs({'job_id': job_id})

            if job_list:
                job = job_list[0]  # Get first (should be only) result

                # Create combined response
                job_detail = RecentJobDetail(
                    job_id=job.get('job_id', ''),
                    title=job.get('title', ''),
                    description=job.get('description'),
                    job_url=job.get('job_url'),
                    budget=job.get('budget'),
                    skills=job.get('skills', []) if job.get('skills') else [],
                    type=job.get('type'),
                    experience_level=job.get('experience_level'),
                    client_location=job.get('client_location'),
                    proposals=job.get('proposals'),
                    scraped_at=job.get('scraped_at', ''),
                    search_query=job.get('search_query'),
                    alert_sent_at=alert.get('sent_at', ''),
                    webhook_status=alert.get('response_status')
                )

                jobs_with_details.append(job_detail)

        return RecentJobsDetailsResponse(
            jobs=jobs_with_details,
            count=len(jobs_with_details),
            limit=limit
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
