"""
backend/integrations - External Service Integrations

This module provides integration layers for external services.
"""

from .selenium_setup import create_driver, configure_driver, cleanup_driver

__all__ = [
    'create_driver',
    'configure_driver',
    'cleanup_driver',
]
