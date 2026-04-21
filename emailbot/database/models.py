"""
Database Models for Alembic Migrations

This module defines SQLAlchemy models that correspond to the database schema.
These models are used by Alembic for autogenerate support and provide a
Python-side representation of the database structure.

Usage:
    from emailbot.database.models import SessionState, Base
    
    # The Base.metadata is used by Alembic for autogenerate
"""

from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, func
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class SessionState(Base):
    """
    Session state table model.
    
    Stores serialized BotState objects as JSON for each user session.
    Supports both SQLite and PostgreSQL databases.
    
    Attributes:
        user_id: Unique identifier for each user session (Primary Key)
        state_json: Serialized JSON representation of BotState
        created_at: Timestamp when the session was first created
        updated_at: Timestamp when the session was last updated
    """
    __tablename__ = 'session_state'
    
    user_id = Column(String(255), primary_key=True, nullable=False)
    state_json = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
    
    def __repr__(self):
        return f"<SessionState(user_id='{self.user_id}', updated_at='{self.updated_at}')>"
    
    def to_dict(self):
        """Convert model to dictionary."""
        return {
            'user_id': self.user_id,
            'state_json': self.state_json,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
