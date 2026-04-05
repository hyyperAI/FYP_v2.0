"""
backend/monitoring - Real-Time Job Monitoring System

This module provides continuous monitoring of Upwork for new job postings.
It includes a dual-layer caching system for efficient job detection and
webhook delivery for instant notifications.

Main Classes:
    - ContinuousMonitor: Main monitoring daemon that runs 24/7
    - JobDetector: Detects new jobs using memory + database caching
    - WebhookHandler: Sends webhook notifications with retry logic
    - MonitoringConfig: Configuration management

Quick Start:
    from backend.monitoring import ContinuousMonitor, MonitoringConfig

    # Create config
    config = MonitoringConfig(
        search_query="Python Developer",
        webhook_url="https://hooks.slack.com/...",
        refresh_interval=60
    )

    # Start monitoring
    monitor = ContinuousMonitor(
        query="Python Developer",
        webhook_url="https://hooks.slack.com/...",
        config=config
    )
    monitor.start()

CLI Usage:
    python -m backend.monitoring.cli start \\
        --query "Python Developer" \\
        --webhook-url "https://hooks.slack.com/..."

For detailed documentation, see: docs/monitoring.md
"""

from .job_detector import JobDetector
from .webhook_handler import WebhookHandler
from .config import MonitoringConfig

# Import main classes for convenience
from .continuous_monitor import ContinuousMonitor

__all__ = [
    'ContinuousMonitor',
    'JobDetector',
    'WebhookHandler',
    'MonitoringConfig'
]
