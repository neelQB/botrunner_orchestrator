"""
Request context module for passing user context to tools.

Uses Python's contextvars to store request-scoped data that tools 
can access without changing their function signatures.
"""

from contextvars import ContextVar
from typing import Optional

# Context variable for current user's ID (used as ChromaDB collection name)
_current_user_id: ContextVar[str] = ContextVar("current_user_id", default="")


def get_current_user_id() -> str:
    """
    Get the current user's ID for use in tools.
    Returns empty string if not set.
    """
    return _current_user_id.get()


def set_current_user_id(user_id: Optional[str]) -> None:
    """
    Set the current user's ID for the duration of the request.
    Called by main.py before running emailagents.
    """

    _current_user_id.set(user_id or "")
