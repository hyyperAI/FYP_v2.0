"""
backend/ai - AI Integration Module

This module provides AI-powered analysis capabilities for job data.
"""

from .minimax_client import MinimaxClient
from .report_generator import ReportGenerator, create_dashboard_chart

__all__ = [
    'MinimaxClient',
    'ReportGenerator',
    'create_dashboard_chart',
]
