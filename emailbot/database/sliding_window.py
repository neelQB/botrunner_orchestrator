from agents import SQLiteSession
from agents.memory import SessionABC
from typing import List, Dict, Any, Optional
import os

class SlidingWindowSession(SessionABC):
    """
    A session wrapper that enforces a sliding window of messages.
    It wraps a standard SQLiteSession (or similar) and truncates history 
    to keep only the last N messages after every addition.
    """
    def __init__(self, session_id: str = "default", window_size: int = 5, db_path: str = ":memory:"):
        # Wrap a standard SQLite session for underlying storage
        # Using :memory: ensures it's ephemeral/fast, matching the previous behavior
        # of the in-memory SummarizingSession used in app_agent.py
        self.underlying = SQLiteSession(session_id=session_id, db_path=db_path)
        self.window_size = window_size

    async def get_items(self) -> List[Dict[str, Any]]:
        return await self.underlying.get_items()

    async def add_items(self, items: List[Dict[str, Any]]) -> None:
        # 1. Add new items to history
        await self.underlying.add_items(items)
        
        # 2. Retrieve the total current history
        history = await self.underlying.get_items()
        
        # 3. If history exceeds our limit, trim the oldest items
        if len(history) > self.window_size:
            # Keep the last window_size items
            trimmed_history = history[-self.window_size:]
            
            # Clear and re-add to enforce the limit
            # Note: This is inefficient for large DBs but fine for :memory: and small N
            await self.underlying.clear_session()
            await self.underlying.add_items(trimmed_history)

    async def pop_item(self) -> Optional[Dict[str, Any]]:
        return await self.underlying.pop_item()

    async def clear_session(self) -> None:
        return await self.underlying.clear_session()
        
    async def get_summary(self) -> str:
        """
        Return a summary of the conversation. 
        For SlidingWindowSession, we don't maintain a separate summary, 
        so we return an empty string or a placeholder.
        """
        return ""

    async def update_summary(self, summary: str) -> None:
        """
        Update the summary. 
        For SlidingWindowSession, this is a no-op as we use a sliding window instead.
        """
        pass
