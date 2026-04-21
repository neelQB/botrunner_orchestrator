"""
Agent Session Manager - SQLAlchemy-backed per-user session management.

Provides a single shared async engine (connection pooling) and a factory
function that returns an isolated SQLAlchemySession for each user.

Usage:
    from emailbot.database.agent_session import get_agent_session, dispose_engine

    session = await get_agent_session(user_id="user-123")
    result  = await Runner.run(agent, "Hello", session=session)

    # On application shutdown
    await dispose_engine()
"""

from typing import Optional

from agents.extensions.memory import SQLAlchemySession
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from emailbot.config import settings

# ---------------------------------------------------------------------------
# Shared async engine — created once at import time, reused across sessions.
# Using pool_pre_ping=True so stale connections are recycled automatically.
# ---------------------------------------------------------------------------
_engine: Optional[AsyncEngine] = None


def _get_engine() -> AsyncEngine:
    """Return (lazily creating) the shared async engine."""
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            settings.sqlalchemy_database_url,
            echo=False,
            pool_pre_ping=True,
        )
        logger.info(
            f"Shared SQLAlchemy async engine created for: {settings.sqlalchemy_database_url}"
        )
    return _engine


async def dispose_engine() -> None:
    """
    Dispose the shared async engine.

    Call this on application shutdown to cleanly close all pooled connections.
    """
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        logger.info("Shared SQLAlchemy async engine disposed")


async def get_agent_session(user_id: str) -> SQLAlchemySession:
    """
    Return a per-user SQLAlchemySession backed by the shared async engine.

    Each user's conversation history is isolated via a unique ``session_id``.
    Table creation is controlled by ``settings.enable_session_creation_tables``.

    Args:
        user_id: Unique identifier for the user.

    Returns:
        SQLAlchemySession bound to this user.

    Raises:
        Exception: If the session cannot be initialised (e.g. DB unreachable).
    """
    try:
        engine = _get_engine()
        session = SQLAlchemySession(
            session_id=user_id,
            engine=engine,
            create_tables=settings.enable_session_creation_tables,
        )
        logger.info(f"SQLAlchemySession initialised for user: {user_id}")
        return session
    except Exception as e:
        logger.error(
            f"Failed to initialise SQLAlchemySession for user {user_id}: {e}",
            exc_info=True,
        )
        raise
