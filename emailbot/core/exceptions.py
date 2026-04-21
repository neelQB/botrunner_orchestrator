"""
Custom Exceptions - Domain-specific exception classes.

This module contains all custom exception classes used throughout
the application. Exceptions are organized by domain and include
helpful error messages and context.

Usage:
    from emailbot.core.exceptions import AgentError, StateValidationError
    
    try:
        # agent operation
    except AgentError as e:
        logger.error(f"Agent failed: {e}")

Exception Hierarchy:
    BotRunnerException (base)
    ├── ConfigurationError
    ├── StateError
    │   ├── StateValidationError
    │   └── StateSerializationError
    ├── AgentError
    │   ├── AgentCreationError
    │   ├── AgentExecutionError
    │   ├── AgentHandoffError
    │   └── AgentTimeoutError
    ├── GuardrailError
    │   ├── InputGuardrailError
    │   └── OutputGuardrailError
    ├── ToolError
    │   ├── ToolExecutionError
    │   └── ToolValidationError
    ├── DatabaseError
    │   ├── SessionNotFoundError
    │   └── DatabaseConnectionError
    └── ExternalServiceError
        ├── LLMProviderError
        └── VectorDBError
"""

from typing import Any, Dict, Optional


# =============================================================================
# BASE EXCEPTION
# =============================================================================


class BotRunnerException(Exception):
    """
    Base exception for all BotRunner application errors.

    All custom exceptions should inherit from this class to enable
    unified error handling throughout the application.

    Attributes:
        message: Human-readable error message
        details: Additional error context (optional)
        original_exception: The original exception that caused this error
    """

    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        original_exception: Optional[Exception] = None,
    ):
        self.message = message
        self.details = details or {}
        self.original_exception = original_exception
        super().__init__(self.message)

    def __str__(self) -> str:
        """Return string representation with details if available."""
        if self.details:
            return f"{self.message} | Details: {self.details}"
        return self.message

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for API responses."""
        return {
            "error": self.__class__.__name__,
            "message": self.message,
            "details": self.details,
        }


# =============================================================================
# CONFIGURATION ERRORS
# =============================================================================


class ConfigurationError(BotRunnerException):
    """
    Raised when there's a configuration error.

    Examples:
        - Missing required environment variable
        - Invalid configuration value
        - Conflicting configuration settings
    """

    pass


class MissingEnvironmentVariableError(ConfigurationError):
    """Raised when a required environment variable is missing."""

    def __init__(self, variable_name: str):
        super().__init__(
            message=f"Required environment variable '{variable_name}' is not set",
            details={"variable": variable_name},
        )


class InvalidConfigurationError(ConfigurationError):
    """Raised when a configuration value is invalid."""

    def __init__(self, key: str, value: Any, expected: str):
        super().__init__(
            message=f"Invalid configuration for '{key}': got '{value}', expected {expected}",
            details={"key": key, "value": value, "expected": expected},
        )


# =============================================================================
# STATE ERRORS
# =============================================================================


class StateError(BotRunnerException):
    """Base exception for state-related errors."""

    pass


class StateValidationError(StateError):
    """
    Raised when state validation fails.

    Examples:
        - Missing required field
        - Invalid field type
        - Business rule violation
    """

    def __init__(self, field: str, reason: str, value: Any = None):
        super().__init__(
            message=f"State validation failed for '{field}': {reason}",
            details={"field": field, "reason": reason, "value": value},
        )


class StateSerializationError(StateError):
    """
    Raised when state serialization/deserialization fails.

    Examples:
        - JSON encoding error
        - Type conversion error
        - Missing class for deserialization
    """

    def __init__(
        self, operation: str, reason: str, original: Optional[Exception] = None
    ):
        super().__init__(
            message=f"State {operation} failed: {reason}",
            details={"operation": operation},
            original_exception=original,
        )


class SessionNotFoundError(StateError):
    """Raised when a session cannot be found."""

    def __init__(self, user_id: str):
        super().__init__(
            message=f"Session not found for user: {user_id}",
            details={"user_id": user_id},
        )


# =============================================================================
# AGENT ERRORS
# =============================================================================


class AgentError(BotRunnerException):
    """Base exception for agent-related errors."""

    def __init__(
        self,
        message: str,
        agent_name: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        original_exception: Optional[Exception] = None,
    ):
        _details = details or {}
        if agent_name:
            _details["agent_name"] = agent_name
        super().__init__(message, _details, original_exception)
        self.agent_name = agent_name


class AgentCreationError(AgentError):
    """
    Raised when agent creation fails.

    Examples:
        - Invalid agent configuration
        - Missing required tools
        - Invalid model specification
    """

    def __init__(self, agent_name: str, reason: str):
        super().__init__(
            message=f"Failed to create agent '{agent_name}': {reason}",
            agent_name=agent_name,
            details={"reason": reason},
        )


class AgentExecutionError(AgentError):
    """
    Raised when agent execution fails.

    Examples:
        - LLM API error
        - Tool execution failure
        - Maximum turns exceeded
    """

    def __init__(
        self, agent_name: str, reason: str, original: Optional[Exception] = None
    ):
        super().__init__(
            message=f"Agent '{agent_name}' execution failed: {reason}",
            agent_name=agent_name,
            details={"reason": reason},
            original_exception=original,
        )


class AgentHandoffError(AgentError):
    """
    Raised when agent handoff fails.

    Examples:
        - Target agent not found
        - Invalid handoff state
        - Callback execution error
    """

    def __init__(self, source_agent: str, target_agent: str, reason: str):
        super().__init__(
            message=f"Handoff from '{source_agent}' to '{target_agent}' failed: {reason}",
            agent_name=source_agent,
            details={
                "source_agent": source_agent,
                "target_agent": target_agent,
                "reason": reason,
            },
        )


class AgentTimeoutError(AgentError):
    """Raised when agent execution times out."""

    def __init__(self, agent_name: str, timeout_seconds: float):
        super().__init__(
            message=f"Agent '{agent_name}' timed out after {timeout_seconds}s",
            agent_name=agent_name,
            details={"timeout_seconds": timeout_seconds},
        )


# =============================================================================
# GUARDRAIL ERRORS
# =============================================================================


class GuardrailError(BotRunnerException):
    """Base exception for guardrail-related errors."""

    pass


class InputGuardrailError(GuardrailError):
    """
    Raised when input guardrail detects an issue.

    Attributes:
        classification: Type of detected issue (e.g., 'prompt_injection')
        is_blocked: Whether the input was blocked
    """

    def __init__(self, classification: str, reason: str, is_blocked: bool = True):
        super().__init__(
            message=f"Input guardrail triggered: {classification} - {reason}",
            details={
                "classification": classification,
                "reason": reason,
                "is_blocked": is_blocked,
            },
        )
        self.classification = classification
        self.is_blocked = is_blocked


class OutputGuardrailError(GuardrailError):
    """
    Raised when output guardrail detects an issue.

    Attributes:
        original_text: The original text that failed validation
        suggested_text: Corrected text suggestion (if available)
    """

    def __init__(
        self,
        reason: str,
        original_text: Optional[str] = None,
        suggested_text: Optional[str] = None,
    ):
        super().__init__(
            message=f"Output guardrail triggered: {reason}",
            details={
                "reason": reason,
                "original_text": original_text[:100] if original_text else None,
                "suggested_text": suggested_text[:100] if suggested_text else None,
            },
        )
        self.original_text = original_text
        self.suggested_text = suggested_text


# =============================================================================
# TOOL ERRORS
# =============================================================================


class ToolError(BotRunnerException):
    """Base exception for tool-related errors."""

    def __init__(
        self,
        message: str,
        tool_name: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        original_exception: Optional[Exception] = None,
    ):
        _details = details or {}
        if tool_name:
            _details["tool_name"] = tool_name
        super().__init__(message, _details, original_exception)
        self.tool_name = tool_name


class ToolExecutionError(ToolError):
    """
    Raised when a tool execution fails.

    Examples:
        - API call failure
        - Invalid input parameters
        - Resource not found
    """

    def __init__(
        self, tool_name: str, reason: str, original: Optional[Exception] = None
    ):
        super().__init__(
            message=f"Tool '{tool_name}' execution failed: {reason}",
            tool_name=tool_name,
            details={"reason": reason},
            original_exception=original,
        )


class ToolValidationError(ToolError):
    """Raised when tool input validation fails."""

    def __init__(self, tool_name: str, parameter: str, reason: str):
        super().__init__(
            message=f"Tool '{tool_name}' validation failed for parameter '{parameter}': {reason}",
            tool_name=tool_name,
            details={"parameter": parameter, "reason": reason},
        )


# =============================================================================
# DATABASE ERRORS
# =============================================================================


class DatabaseError(BotRunnerException):
    """Base exception for database-related errors."""

    pass


class DatabaseConnectionError(DatabaseError):
    """Raised when database connection fails."""

    def __init__(
        self, database_type: str, reason: str, original: Optional[Exception] = None
    ):
        super().__init__(
            message=f"Database connection failed ({database_type}): {reason}",
            details={"database_type": database_type, "reason": reason},
            original_exception=original,
        )


class DatabaseOperationError(DatabaseError):
    """Raised when a database operation fails."""

    def __init__(
        self, operation: str, reason: str, original: Optional[Exception] = None
    ):
        super().__init__(
            message=f"Database operation '{operation}' failed: {reason}",
            details={"operation": operation, "reason": reason},
            original_exception=original,
        )


# =============================================================================
# EXTERNAL SERVICE ERRORS
# =============================================================================


class ExternalServiceError(BotRunnerException):
    """Base exception for external service errors."""

    def __init__(
        self,
        service_name: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        original_exception: Optional[Exception] = None,
    ):
        _details = details or {}
        _details["service_name"] = service_name
        super().__init__(message, _details, original_exception)
        self.service_name = service_name


class LLMProviderError(ExternalServiceError):
    """
    Raised when an LLM provider fails.

    Examples:
        - Rate limit exceeded
        - API key invalid
        - Model not available
    """

    def __init__(
        self,
        provider: str,
        reason: str,
        model: Optional[str] = None,
        original: Optional[Exception] = None,
    ):
        details = {"reason": reason}
        if model:
            details["model"] = model
        super().__init__(
            service_name=provider,
            message=f"LLM provider '{provider}' error: {reason}",
            details=details,
            original_exception=original,
        )


class VectorDBError(ExternalServiceError):
    """Raised when vector database operations fail."""

    def __init__(
        self,
        db_type: str,
        operation: str,
        reason: str,
        original: Optional[Exception] = None,
    ):
        super().__init__(
            service_name=f"VectorDB ({db_type})",
            message=f"Vector DB '{db_type}' {operation} failed: {reason}",
            details={"db_type": db_type, "operation": operation, "reason": reason},
            original_exception=original,
        )


class CalendlyError(ExternalServiceError):
    """Raised when Calendly API operations fail."""

    def __init__(
        self, operation: str, reason: str, original: Optional[Exception] = None
    ):
        super().__init__(
            service_name="Calendly",
            message=f"Calendly {operation} failed: {reason}",
            details={"operation": operation, "reason": reason},
            original_exception=original,
        )


# =============================================================================
# PROBING ERRORS
# =============================================================================


class ProbingError(BotRunnerException):
    """Base exception for probing-related errors."""

    pass


class ProbingQuestionGenerationError(ProbingError):
    """Raised when probing question generation fails."""

    def __init__(self, reason: str, original: Optional[Exception] = None):
        super().__init__(
            message=f"Failed to generate probing questions: {reason}",
            details={"reason": reason},
            original_exception=original,
        )


# =============================================================================
# BOOKING ERRORS
# =============================================================================


class BookingError(BotRunnerException):
    """Base exception for booking-related errors."""

    pass


class BookingValidationError(BookingError):
    """Raised when booking validation fails."""

    def __init__(self, field: str, reason: str):
        super().__init__(
            message=f"Booking validation failed for '{field}': {reason}",
            details={"field": field, "reason": reason},
        )


class SlotUnavailableError(BookingError):
    """Raised when a requested time slot is not available."""

    def __init__(self, requested_date: str, requested_time: str):
        super().__init__(
            message=f"Requested slot is not available: {requested_date} at {requested_time}",
            details={"date": requested_date, "time": requested_time},
        )


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================


def handle_exception(
    exception: Exception, context: Optional[Dict[str, Any]] = None
) -> BotRunnerException:
    """
    Convert any exception to a BotRunnerException.

    Useful for wrapping third-party exceptions in our custom hierarchy.

    Args:
        exception: The exception to wrap
        context: Additional context to include

    Returns:
        A BotRunnerException instance
    """
    if isinstance(exception, BotRunnerException):
        # Already our exception type
        if context:
            exception.details.update(context)
        return exception

    # Wrap in generic BotRunnerException
    return BotRunnerException(
        message=str(exception), details=context or {}, original_exception=exception
    )
