# Changelog

All notable changes to the BotRunner project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2024-XX-XX

### Added

#### Configuration System

- **`app/config/settings.py`**: Environment-based configuration using Pydantic BaseSettings
  - All settings loaded from environment variables with validation
  - Support for multiple database backends (SQLite, Neon PostgreSQL)
  - Support for multiple vector DBs (ChromaDB, Qdrant)
  - Model routing configuration (OpenAI, Azure, Gemini)
- **`app/config/constants.py`**: Centralized constants and enumerations
  - `AgentName` enum for all agent types
  - `BookingType` enum for demo booking types
  - `LeadClassification` enum for lead scoring
  - `DatabaseType` and `VectorDBType` enums
  - Immutable constants (MAX_HISTORY, thresholds, etc.)

#### Domain Models

- **`app/core/models.py`**: All models converted to Pydantic v2
  - `BotState`: Top-level state container with validation
  - `UserContext`: User session data with field validators
  - `BotPersona`: Bot configuration with defaults
  - `BotResponse`: Structured agent response output
  - `ContactDetails`: Contact information with email validation
  - `Products`: Product/service definitions
  - `InputGuardrail` / `OutputGuardrail`: Guardrail result models
  - `ProbingQuestion` / `ProbingContext` / `ProbingOutput`: Probing system models
  - `LeadAnalysis`: Lead qualification data
  - `FollowupDetails` / `ProceedEmailDetails`: Specialized agent outputs
  - `BotRequest` / `APIResponse`: API data models

#### Exception System

- **`app/core/exceptions.py`**: Domain-specific exception hierarchy
  - `BotRunnerException`: Base exception class
  - `ConfigurationError`: Configuration-related errors
  - `StateError`: State validation/management errors
  - `AgentError` hierarchy: Agent-specific errors
  - `GuardrailError` hierarchy: Input/output guardrail errors
  - `ToolError` hierarchy: Tool execution errors
  - `DatabaseError` hierarchy: Database operation errors
  - `ExternalServiceError` hierarchy: External API errors

#### Agent System

- **`app/agents/base.py`**: Base classes and protocols
  - `AgentConfig`: Pydantic model for agent configuration
  - `AgentProtocol`: Interface for agent implementations
  - `BaseAgent`: Abstract base class with generic typing
  - `InstructionGenerator`: Protocol for dynamic instructions
  - `HandoffCallback`: Protocol for handoff callbacks

- **`app/agents/definitions.py`**: Concrete agent implementations
  - Dynamic instruction generators for all agents
  - Factory functions: `create_sales_agent()`, `create_demo_booking_agent()`, etc.
  - All agents use `RouterModel` for LLM routing
  - Proper tool and handoff configuration

- **`app/agents/factory.py`**: Agent factory pattern
  - `AgentFactory`: Singleton factory with agent caching
  - Creator registration for extensibility
  - `create_root_agent()`: Builds complete agent graph
  - Convenience functions: `root_agent()`, `sales_agent()`, etc.

#### Callbacks System

- **`app/callbacks/handlers.py`**: Handoff callback implementations
  - `on_sales_handoff()`: Handles handoff to sales agent
  - `on_demo_handoff()`: Handles handoff to demo booking
  - `on_followup_handoff()`: Handles handoff to follow-up
  - `on_human_handoff()`: Handles escalation to human
  - `CallbackRegistry`: Registry for callback management
  - All callbacks traced with `@track` decorator

#### Instructions System

- **`app/instructions/generators.py`**: Dynamic instruction generation
  - `InstructionBuilder`: Fluent builder for instructions
  - `PromptTemplate`: Reusable prompt templates
  - `CompositePromptBuilder`: Combine multiple prompts
  - Helper functions for formatting history and fields

#### Documentation

- **`docs/ARCHITECTURE.md`**: System architecture documentation
- **`docs/API.md`**: API endpoint documentation
- **`docs/CHANGELOG.md`**: This changelog file

### Changed

#### State Management

- **`app/core/state.py`**: Now re-exports from `models.py` for backward compatibility
  - All `dataclass` implementations replaced with Pydantic models
  - Import paths unchanged for existing code

#### Guardrails

- **`app/core/guardrail.py`**: Refactored for better structure
  - Module-level state for guardrail decisions
  - Proper error handling with logging
  - Utility functions for creating guardrail results
  - Uses new model imports from `app.core.models`

#### Application Entry Point

- **`app_agent.py`**: Updated to use new modular structure
  - Imports from new `app.config` and `app.core.models`
  - Uses `AgentFactory` for agent creation
  - Pydantic `model_copy()` instead of dataclass `replace()`
  - Extracted helper functions for better testability:
    - `_extract_output_data()`
    - `_get_last_agent_name()`
    - `_apply_output_to_state()`
    - `_update_chat_history()`
    - `_update_chat_summary()`
    - `_update_executive_summary()`
    - `_update_probing_context()`
    - `_initialize_session()`
    - `_retrieve_cached_pairs()`
    - `_build_agent_input()`
    - `_execute_agent()`
    - `_handle_guardrail_tripwire()`

#### Tools Module

- **`app/tools/__init__.py`**: Created package init with re-exports
  - Centralizes all tool exports
  - Maintains backward compatibility

### Not Changed (Per Requirements)

The following components were intentionally NOT modified:

- **RAG Code** (`rag/`): Vector DB integration remains unchanged
- **Database Layer**:
  - `app/database/summarizer.py`
  - `app/database/session_manager.py`
  - `app/database/cachememory.py`
- **Prompt Content** (`app/prompts/`): Prompt text unchanged
- **`main.py` Structure**: Enhanced but structure preserved

### Deprecated

- Direct instantiation of dataclasses from `state.py` - use Pydantic models instead
- Manual agent creation - use `AgentFactory` instead

### Migration Guide

#### Importing Models

```python
# Old way (still works)
from emailbot.core.state import BotState, UserContext

# New way (preferred)
from emailbot.core.models import BotState, UserContext
```

#### Creating State

```python
# Old way (dataclass)
from dataclasses import replace
state = BotState(...)
new_state = replace(state, response="Hello")

# New way (Pydantic)
state = BotState(...)
new_state = state.model_copy(update={"response": "Hello"})
```

#### Using Agents

```python
# Old way
from emailbot.agent.my_agents import root_agent
agent = root_agent()

# New way
from emailbot.agents import root_agent
agent = root_agent()

# Or use factory
from emailbot.agents import AgentFactory
factory = AgentFactory.get_instance()
agent = factory.create_agent("root_agent")
```

#### Configuration

```python
# Old way
import os
api_key = os.getenv("OPENAI_API_KEY")

# New way
from emailbot.config import settings
api_key = settings.openai_api_key
```

#### Error Handling

```python
# Old way
try:
    result = await runner.run(...)
except Exception as e:
    logger.error(f"Error: {e}")

# New way
from emailbot.core.exceptions import AgentExecutionError, GuardrailError

try:
    result = await runner.run(...)
except AgentExecutionError as e:
    logger.error(f"Agent failed: {e}")
except GuardrailError as e:
    logger.warning(f"Guardrail triggered: {e}")
```

### Technical Debt Addressed

1. **Type Safety**: All models now have runtime validation via Pydantic
2. **Configuration**: Centralized, validated configuration system
3. **Error Handling**: Domain-specific exceptions with proper hierarchy
4. **Code Organization**: Clear separation of concerns with modular packages
5. **Documentation**: Comprehensive architecture and API docs
6. **Testability**: Extracted functions and dependency injection support

### Known Issues

- None currently documented

### Contributors

- Refactoring: GitHub Copilot

---

## [1.0.0] - Previous Version

Initial release with:

- Multi-agent orchestration using OpenAI Agents SDK
- RAG integration with ChromaDB/Qdrant
- Calendly booking integration
- Semantic conversation cache
- Input/output guardrails
- Streamlit UI
