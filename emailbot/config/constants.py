"""
Application Constants - Immutable values and enumerations.

This module contains all constants, enumerations, and fixed values
used throughout the application. These values should not change
during runtime.

Usage:
    from emailbot.config.constants import MAX_HISTORY, AgentName, BookingType
    
    if agent == AgentName.SALES:
        ...
"""

from enum import Enum, auto
from typing import Final


# =============================================================================
# DATABASE CONSTANTS
# =============================================================================


class DatabaseType(str, Enum):
    """Supported database types."""

    SQLITE = "sqlite"
    NEON = "neon"
    POSTGRES = "postgres"
    
# =============================================================================
# HISTORY & SUMMARIZATION LIMITS
# =============================================================================

MAX_HISTORY: Final[int] = 15
"""Maximum number of chat history messages to retain."""

SUMMARIZE_CONTEXT_LENGTH: Final[int] = 3
"""Number of message pairs before triggering summarization."""

SUMMARIZE_KEEP_LAST_N_TURNS: Final[int] = 3
"""Number of recent turns to keep verbatim (not summarized)."""

EXECUTIVE_SUMMARY_TRIGGER: Final[int] = 15
"""Number of messages before generating executive summary."""


# =============================================================================
# AGENT CONSTANTS
# =============================================================================


class AgentName(str, Enum):
    """Agent identifiers used in the system."""

    MAIN = "main_agent"
    SALES = "sales_agent"
    CTA = "cta_agent"
    FOLLOWUP = "followup_agent"
    HUMAN = "human_agent"
    LEAD_ANALYSIS = "lead_analysis_agent"
    PROBING = "probing_agent"
    INPUT_GUARDRAIL = "input_guardrail_agent"
    OUTPUT_GUARDRAIL = "output_guardrail_agent"
    NEGOTIATION_ENGINE = "negotiation_engine_agent"
    ASSET_SHARING = "asset_sharing_agent"
    OBJECTION_HANDLE = "objection_handle_agent"
    RESPONSE_FORMATTER = "response_formatter_agent"


# Agent handoff descriptions
AGENT_HANDOFF_DESCRIPTIONS: Final[dict] = {
    AgentName.SALES: (
        "Used for handling user's query when user communicates about products "
        "or company related details. 'ask about your products', 'pricing details', "
        "'features', 'company info', etc."
    ),
    AgentName.CTA: (
        "Used for handling Call To Action (CTA) requests, specifically for "
        "providing subscription links or plan activation details. Hand off "
        "when the user is convinced to subscribe to any plan, asks for a "
        "subscription link, or wants to proceed with activation."
    ),
    AgentName.FOLLOWUP: (
        "Used for handling user's query when user wants followup later OR is "
        "responding to a follow-up scheduling question. Hand off when user says "
        "'ping me in 5 min', 'remind me later', 'contact me tomorrow'."
    ),
    AgentName.HUMAN: (
        "Used when user explicitly requests to speak with a human agent, "
        "customer support, or real person. Hand off when user says: "
        "'talk to human', 'connect me with someone', 'I want to speak with your team'."
    ),
}


# =============================================================================
# BOOKING CONSTANTS
# =============================================================================


class BookingType(str, Enum):
    """Types of booking operations."""

    NEW = "new"
    RESCHEDULE = "reschedule"
    CANCEL = "cancel"


class BookingStatus(str, Enum):
    """Booking status values."""

    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    RESCHEDULED = "rescheduled"


# Default booking time if not specified
DEFAULT_BOOKING_HOUR: Final[int] = 10
DEFAULT_BOOKING_MINUTE: Final[int] = 0


# =============================================================================
# LEAD CLASSIFICATION
# =============================================================================


class LeadClassification(str, Enum):
    """Lead quality classifications."""

    HOT = "hot"
    WARM = "warm"
    COLD = "cold"


class UrgencyLevel(str, Enum):
    """Lead urgency levels."""

    IMMEDIATE = "immediate"
    SOON = "soon"
    LATER = "later"
    NO_INTEREST = "no-interest"


# =============================================================================
# GUARDRAIL CONSTANTS
# =============================================================================


class AttackClassification(str, Enum):
    """Types of detected attacks."""

    PROMPT_INJECTION = "prompt_injection"
    JAILBREAK = "jailbreak"
    DATA_EXTRACTION = "data_extraction"
    HARMFUL_CONTENT = "harmful_content"
    OFF_TOPIC = "off_topic"
    NONE = "none"


# =============================================================================
# API CONSTANTS
# =============================================================================

# Request timeouts (seconds)
API_TIMEOUT: Final[int] = 30
LLM_TIMEOUT: Final[int] = 60

# Rate limiting
MAX_RETRIES: Final[int] = 3
RETRY_DELAY: Final[float] = 1.0

# Allowed fallback errors for LiteLLM
ALLOWED_FALLBACK_ERRORS: Final[list] = [
    "rate_limit",
    "insufficient_quota",
    "timeout",
    "internal_server_error",
    "bad_gateway",
    "service_unavailable",
    "context_length_exceeded",
    "authentication_error",
    "invalid_request_error",
    "unauthorized_error",
    "forbidden_error",
    "not_found_error",
    "authentication",
    "invalid_api_key",
    "AuthenticationError",
]


# =============================================================================
# PROBING CONSTANTS
# =============================================================================

DEFAULT_PROBING_THRESHOLD: Final[int] = 50
"""Default score threshold for probing completion."""

DEFAULT_OBJECTION_LIMIT: Final[int] = 3
"""Default number of objections before stopping probing."""

DEFAULT_RESET_COUNT_LIMIT: Final[int] = 2
"""Default limit for objection reset cycles."""

DEFAULT_PROBING_QUESTIONS_COUNT: Final[int] = 5
"""Default number of probing questions to generate."""


# =============================================================================
# EMOJI & DISPLAY
# =============================================================================

EMOJI: Final[dict] = {
    "success": "✅",
    "error": "❌",
    "warning": "⚠️",
    "info": "ℹ️",
    "question": "❓",
    "calendar": "📅",
    "time": "⏰",
    "email": "📧",
    "phone": "📞",
    "user": "👤",
    "bot": "🤖",
    "wave": "👋",
    "clipboard": "📋",
    "rocket": "🚀",
    "star": "⭐",
    "fire": "🔥",
    "check": "✓",
}
