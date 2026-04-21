"""
Tools Package - Tool implementations for emailagents.

This package provides tools that extend agent capabilities including:
- RAG/retrieval tools
- Booking and scheduling tools
- Validation tools
- Utility tools

Usage:
    from emailbot.tools import retrieve_query, validate_datetime
    
    # Tools are used with @function_tool decorator
"""

# Import all tools for convenience
from emailbot.tools.sales_tools import retrieve_query
from emailbot.tools.booking_tools import (
    parse_relative_time,
    validate_datetime,
    convert_time_to_utc,
)
from emailbot.tools.followup_timezone import get_timezone, process_followup_datetime
from emailbot.tools.human_tools import validate_email

__all__ = [
    # Sales tools
    "retrieve_query",
    # Booking tools
    "parse_relative_time",
    "validate_datetime",
    "convert_time_to_utc",
    # Timezone tools
    "get_timezone",
    "process_followup_datetime",
    # Human tools
    "validate_email",
]
