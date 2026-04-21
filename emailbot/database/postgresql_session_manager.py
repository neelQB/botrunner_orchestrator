
import json
from typing import Any, Dict, List, Optional
# Load environment variables FIRST before importing config
from loguru import logger
# Import from new modular structure
from emailbot.config import settings, MAX_HISTORY
from emailbot.database.sliding_window import SlidingWindowSession
from agents.extensions.memory import SQLAlchemySession



# Context-limited session wrapper
class ContextLimitedSession:
    """
    Wrapper around SQLAlchemySession that enforces a context window limit.
    
    This ensures only the last N messages are retrieved from the database,
    preventing all history from being passed to the agent.
    """    
    def __init__(self, session: SQLAlchemySession, context_window_size: int):
        """
        Initialize wrapper.
        
        Args:
            session: Underlying SQLAlchemySession
            context_window_size: Max messages to retrieve (last N only)
        """
        self.session = session
        self.context_window_size = context_window_size
        logger.info(f"ContextLimitedSession wrapper initialized with window_size={context_window_size}")
    
    async def get_items(self, limit: int = None) -> List[Dict[str, Any]]:
        """
        Get items with enforced context limit, validating tool call chains.
        
        CRITICAL: OpenAI requires that messages with role='tool' must follow
        assistant messages with tool_calls. This method skips orphaned tool
        messages that don't have corresponding assistant tool_calls, while
        preserving recent context.
        
        If limit is not specified, uses context_window_size.
        Returns at most context_window_size items (may be less if orphaned
        tool messages are removed).
        """
        effective_limit = limit or self.context_window_size
        # Enforce maximum limit
        effective_limit = min(effective_limit, self.context_window_size)
        logger.debug(f"Fetching {effective_limit} items (context window: {self.context_window_size})")
        
        # Get items from session
        items = await self.session.get_items(limit=effective_limit)
        if not items:
            logger.debug(f"Retrieved {len(items)} items from session")
            return items
        
        # Validate tool call chains - ensure no orphaned tool messages
        validated_items = self._validate_tool_chains(items)
        
        if len(validated_items) < len(items):
            logger.warning(
                f"Skipped {len(items) - len(validated_items)} orphaned tool message(s). "
                f"Retrieved: {len(items)}, after validation: {len(validated_items)}"
            )
        
        logger.debug(f"Retrieved {len(validated_items)} items from session after tool chain validation")
        return validated_items
    
    def _validate_tool_chains(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Ensure all tool messages have their corresponding tool_call messages.
        
        Skips any tool message that references a non-existent tool_call_id,
        while continuing to process subsequent messages (preserving recent context).
        
        This is CRITICAL because OpenAI's API rejects messages with role='tool' that don't
        have a corresponding assistant message with tool_calls before them.
        
        Args:
            items: List of message items from session
        
        Returns:
            Validated list with orphaned tool messages removed (won't trigger OpenAI API errors)
        """
        if not items:
            return items
        
        logger.debug(f"Validating tool chains for {len(items)} items")
        
        # First pass: identify all tool_call_ids from assistant messages
        available_tool_calls = set()
        
        for idx, item in enumerate(items):
            role = item.get("role", "")
            
            # Only assistant messages can initiate tool calls
            if role == "assistant":
                # Check if this assistant message has tool_calls in its output
                # The emailagents SDK stores tool call responses in various formats
                content = item.get("content", "")
                
                # Format 1: Direct string with tool_call_id field
                if "tool_call_id" in str(content):
                    try:
                        # Try parsing as JSON if it looks like JSON
                        if isinstance(content, str) and (content.startswith('{') or '{"' in content):
                            parsed = json.loads(content)
                            if "tool_call_id" in parsed:
                                call_id = parsed.get("tool_call_id")
                                available_tool_calls.add(call_id)
                                logger.debug(f"Found assistant tool_call at index {idx}: {call_id}")
                    except (json.JSONDecodeError, TypeError, ValueError):
                        pass
                
                # Format 2: OpenAI standard tool_calls field (if SDK uses it)
                if "tool_calls" in item:
                    tool_calls = item.get("tool_calls", [])
                    for tc in tool_calls:
                        if isinstance(tc, dict) and "id" in tc:
                            available_tool_calls.add(tc["id"])
                            logger.debug(f"Found OpenAI tool_call at index {idx}: {tc['id']}")
        
        logger.debug(f"Available tool_call_ids: {available_tool_calls}")
        
        # Second pass: validate all tool messages have corresponding tool_calls
        valid_items = []
        skipped_orphaned = 0
        
        for idx, item in enumerate(items):
            role = item.get("role", "")
            
            if role == "tool":
                tool_call_id = item.get("tool_call_id")
                
                # Tool messages MUST have a valid tool_call_id
                if not tool_call_id:
                    logger.error(
                        f"ERROR: Tool message at index {idx} is missing tool_call_id. "
                        f"This is a data corruption issue. Skipping malformed message."
                    )
                    skipped_orphaned += 1
                    continue
                
                # Check if this tool message references a valid tool_call
                if tool_call_id not in available_tool_calls:
                    skipped_orphaned += 1
                    logger.warning(
                        f"SKIPPING orphaned tool message at index {idx}: "
                        f"tool_call_id='{tool_call_id}' does not exist in preceding assistant messages. "
                        f"Available: {available_tool_calls}. "
                        f"This occurs when context window is too small and cuts off tool interactions. "
                        f"RECOMMENDATION: Increase SESSION_CONTEXT_WINDOW_SIZE (currently {self.context_window_size}) "
                        f"if you see this warning frequently."
                    )
                    # Skip only this message, continue processing rest to preserve recent context
                    continue
            
            # Add valid items (skipped orphaned tool messages above)
            valid_items.append(item)
        
        if skipped_orphaned > 0:
            logger.warning(
                f"Tool chain validation skipped {skipped_orphaned} orphaned message(s). "
                f"Returned {len(valid_items)} of {len(items)} items "
                f"(kept recent context by only removing bad tool messages)."
            )
        
        return valid_items
    
    async def add_items(self, items: List[Dict[str, Any]]) -> None:
        """Pass through to underlying session."""
        return await self.session.add_items(items)
    
    async def pop_item(self) -> Optional[Dict[str, Any]]:
        """Pass through to underlying session."""
        return await self.session.pop_item()
    
    async def clear_session(self) -> None:
        """Pass through to underlying session."""
        return await self.session.clear_session()
    
    async def get_summary(self) -> str:
        """Pass through to underlying session."""
        return await self.session.get_summary()



async def _init_session(user_id: str = None):
    """
    Initialize SQLAlchemySession with context window limit for a specific user.
    
    IMPORTANT: Each user MUST have their own session_id to prevent
    conversation history from being mixed between users.
    
    Args:
        user_id: Unique identifier for the user. If None, uses global session
                 (only for testing/single-user scenarios)
    
    Returns:
        ContextLimitedSession wrapper that enforces context_window_size limit
    
    Supports multiple database backends via SQLAlchemy:
    - PostgreSQL (postgresql+asyncpg://user:pass@host/db)
    - MySQL (mysql+aiomysql://user:pass@host/db)
    - SQLite (sqlite+aiosqlite:///path/to/db.db)
    """
    # Use user_id if provided, otherwise fall back to global session
    session_id = user_id or settings.sessions_id
    
    # Create a per-user session - NOT using global cache
    # Each user gets their own SQLAlchemySession instance
    try:
        underlying_session = SQLAlchemySession.from_url(
            session_id=session_id,
            url=settings.sqlalchemy_database_url,
            create_tables=settings.enable_session_creation_tables,
        )
        logger.info(f"SQLAlchemySession initialized for user {session_id}")
    except Exception as e:
        logger.error(f"Failed to initialize SQLAlchemySession for user {session_id}: {e}", exc_info=True)
        raise
    
    return underlying_session


# Replaced SlidingWindowSession with standard SQLAlchemySession configuration globally if needed.
# For now, we will just export sessions as None or allow the main script to use _init_session.
sessions = None
