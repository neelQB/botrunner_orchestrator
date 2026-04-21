"""
Configuration Package - Environment-based configuration management.

This module provides centralized configuration for the application,
supporting multiple environments (development, staging, production).

Usage:
    from emailbot.config import settings, constants
    
    # Access settings
    database_url = settings.database_url
    
    # Access constants
    max_history = constants.MAX_HISTORY
"""

from emailbot.config.settings import Settings, get_settings, logger
from emailbot.config.constants import (
    # Database
    DatabaseType,
    # Limits
    MAX_HISTORY,
    SUMMARIZE_CONTEXT_LENGTH,
    SUMMARIZE_KEEP_LAST_N_TURNS,
    # Agent names
    AgentName,
    # Booking types
    BookingType,
    # Lead classifications
    LeadClassification,
    UrgencyLevel,
)

# Global settings instance
settings = get_settings()

__all__ = [
    # Settings
    "Settings",
    "settings",
    "get_settings",
    "logger",
    # Constants
    "DatabaseType",
    "MAX_HISTORY",
    "SUMMARIZE_CONTEXT_LENGTH",
    "SUMMARIZE_KEEP_LAST_N_TURNS",
    "AgentName",
    "BookingType",
    "LeadClassification",
    "UrgencyLevel",
]
