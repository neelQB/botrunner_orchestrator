# BotRunner Developer Guide

> **Last Updated:** February 6, 2026 &nbsp;|&nbsp; **Version:** 2.0.0

---

## Table of Contents

- [Development Environment Setup](#development-environment-setup)
- [Code Structure & Organization](#code-structure--organization)
- [Development Workflows](#development-workflows)
- [API Documentation](#api-documentation)
- [Common Development Tasks](#common-development-tasks)
- [Debugging & Troubleshooting](#debugging--troubleshooting)
- [Best Practices](#best-practices)
- [Contributing Code](#contributing-code)

---

## Development Environment Setup

### Prerequisites

| Requirement           | Version  | Purpose            |
| --------------------- | -------- | ------------------ |
| Python                | 3.11+    | Runtime            |
| pip                   | Latest   | Package management |
| Git                   | Latest   | Version control    |
| SQLite                | Built-in | Dev database       |
| VS Code (recommended) | Latest   | IDE                |

### Step-by-Step Setup

```bash
# 1. Clone the repository
git clone <repository-url>
cd botrunner

# 2. Create virtual environment
python -m venv .venv

# 3. Activate virtual environment
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Copy environment configuration
cp .env_example .env

# 6. Set minimum required environment variables in .env:
#    OPENAI_API_KEY=sk-your-key
#    DATABASE=SQLite
#    VECTORDB=chromadb

# 7. Initialize database (happens automatically on first startup)
# 8. Start the development server
uvicorn main:emailbot --host 0.0.0.0 --port 8000 --reload
```

### IDE Configuration (VS Code)

Recommended extensions:

- **Python** — Microsoft Python extension
- **Pylance** — Type checking
- **Python Debugger** — Debugging support

Recommended settings (`.vscode/settings.json`):

```json
{
  "python.analysis.typeCheckingMode": "basic",
  "python.analysis.autoImportCompletions": true,
  "editor.formatOnSave": true,
  "python.formatting.provider": "black"
}
```

### Debugging Setup

Create `.vscode/launch.json`:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "FastAPI Server",
      "type": "debugpy",
      "request": "launch",
      "module": "uvicorn",
      "args": [
        "main:emailbot",
        "--host",
        "0.0.0.0",
        "--port",
        "8000",
        "--reload"
      ],
      "jinja": true,
      "env": {
        "ENVIRONMENT": "development",
        "DEBUG": "true"
      }
    },
    {
      "name": "Run Tests",
      "type": "debugpy",
      "request": "launch",
      "program": "${file}",
      "console": "integratedTerminal"
    }
  ]
}
```

---

## Code Structure & Organization

### Directory Layout

```
botrunner/
├── main.py                  # FastAPI entry point, endpoint definitions
├── app_agent.py             # Chatbot execution pipeline
├── app/
│   ├── agents/              # Agent definitions (modern architecture)
│   │   ├── base.py          # AgentConfig, AgentProtocol, BaseAgent
│   │   ├── definitions.py   # Creator functions + dynamic instruction generators
│   │   └── factory.py       # AgentFactory with singleton caching
│   ├── agent/               # Standalone agents (not part of main handoff graph)
│   │   ├── crawl_persona_agent.py
│   │   ├── probing_agent.py
│   │   └── probing_instruction_agent.py
│   ├── apis/                # External API integrations
│   │   └── calendly_api.py
│   ├── callbacks/           # Handoff callback handlers
│   │   └── handlers.py
│   ├── config/              # Configuration
│   │   ├── settings.py      # Pydantic BaseSettings
│   │   └── constants.py     # Enums, constants
│   ├── core/                # Core domain logic
│   │   ├── models.py        # All Pydantic models (20+)
│   │   ├── exceptions.py    # Exception hierarchy (15+ classes)
│   │   ├── guardrail.py     # Input/output guardrails
│   │   ├── probing.py       # ProbingEngine
│   │   ├── request_context.py # Thread-safe context variables
│   │   └── state.py         # Backward-compatible re-exports
│   ├── database/            # Persistence layer
│   │   ├── session_manager.py
│   │   ├── cachememory.py
│   │   ├── summarizer.py
│   │   └── executive_summary.py
│   ├── instructions/        # Dynamic instruction builders
│   │   └── generators.py
│   ├── prompts/             # Prompt templates (18 modules)
│   ├── route/               # LLM routing
│   │   └── route.py
│   ├── tools/               # Agent tools
│   │   ├── sales_tools.py
│   │   ├── booking_tools.py
│   │   ├── followup_timezone.py
│   │   └── human_tools.py
│   └── utils/
│       ├── prompt_cache.py
│       └── utils.py
```

### Naming Conventions

| Item            | Convention                                    | Example                            |
| --------------- | --------------------------------------------- | ---------------------------------- |
| Files           | `snake_case.py`                               | `booking_tools.py`                 |
| Classes         | `PascalCase`                                  | `AgentFactory`, `BotState`         |
| Functions       | `snake_case`                                  | `create_sales_agent()`             |
| Constants       | `UPPER_SNAKE_CASE`                            | `MAX_HISTORY`, `CACHE_BREAK`       |
| Enums           | `PascalCase` class, `UPPER_SNAKE_CASE` values | `AgentName.SALES`                  |
| Pydantic models | `PascalCase`                                  | `ContactDetails`, `BotPersona`     |
| Tools           | `snake_case` with `@function_tool`            | `retrieve_query`, `validate_email` |
| Prompts         | `snake_case_prompt()`                         | `sales_prompt()`, `demo_prompt()`  |

### Module Dependencies

```
main.py
  └── app_agent.py
        ├── app/agents/factory.py
        │     └── app/agents/definitions.py
        │           ├── app/prompts/*
        │           ├── app/tools/*
        │           └── app/route/route.py
        ├── app/core/guardrail.py
        ├── app/core/probing.py
        ├── app/database/*
        └── app/utils/prompt_cache.py
```

---

## Development Workflows

### How to Create a New Agent

1. **Define the agent name** in `app/config/constants.py`:

```python
class AgentName(str, Enum):
    MY_NEW_AGENT = "my_new_agent"
```

2. **Create a prompt** in `app/prompts/my_agent.py`:

```python
from emailbot.core.models import BotState
from emailbot.utils.prompt_cache import CACHE_BREAK

def my_agent_prompt(state: BotState) -> str:
    persona = state.bot_persona
    context = state.user_context

    # Static part (cacheable)
    static = f"""You are {persona.name}, a specialized assistant for {persona.company_name}.

Your role is to [describe purpose].

## Rules
- Rule 1
- Rule 2

## Output Format
Respond in JSON matching the BotResponse schema.
"""

    # Dynamic part (per-request)
    dynamic = f"""
## Current Context
- User: {context.user_id}
- Query: {context.user_query}
- Chat Summary: {context.chat_summary}
"""

    return f"{static}{CACHE_BREAK}{dynamic}"
```

3. **Register the prompt** in `app/prompts/__init__.py`:

```python
from emailbot.prompts.my_agent import my_agent_prompt
```

4. **Create a dynamic instruction generator** in `app/agents/definitions.py`:

```python
@track
def dynamic_my_agent_instructions(context, agent) -> str:
    try:
        from emailbot.prompts.my_agent import my_agent_prompt
        state = context.context
        return my_agent_prompt(state)
    except Exception as e:
        logger.error(f"Error generating my_agent instructions: {e}")
        return "Fallback instructions here."
```

5. **Create the agent** in `app/agents/definitions.py`:

```python
def create_my_new_agent() -> Agent:
    return Agent(
        name=AgentName.MY_NEW_AGENT,
        handoff_description="When to hand off to this agent...",
        instructions=dynamic_my_agent_instructions,
        model=get_primary_model(),
        model_settings=get_model_settings(),
        tools=[],  # Add tools as needed
        output_type=get_output_schema(),
    )
```

6. **Register in the factory** in `app/agents/factory.py`:

```python
from emailbot.emailagents.definitions import create_my_new_agent

class AgentFactory:
    def __init__(self):
        self._creators = {
            # ... existing emailagents ...
            AgentName.MY_NEW_AGENT: create_my_new_agent,
        }
```

7. **Add handoff** (if the root agent should route to it) in `factory.py`'s `create_root_agent()`:

```python
my_agent = self.create_agent(AgentName.MY_NEW_AGENT)
# Add to handoffs list:
handoffs=[
    # ... existing handoffs ...
    handoff(agent=my_agent, on_handoff=on_my_agent_handoff),
]
```

8. **Create a callback** (optional) in `app/callbacks/handlers.py`:

```python
@track
def on_my_agent_handoff(ctx: RunContextWrapper[BotState]) -> BotState:
    state = ctx.context
    # Update state as needed
    return state
```

### How to Add a New Tool

1. **Create the tool** in the appropriate file under `app/tools/`:

```python
from agents import function_tool
from emailbot.config.settings import

@function_tool
def my_new_tool(param1: str, param2: int = 10) -> dict:
    """
    Tool description that the LLM will see.

    Args:
        param1: Description of param1
        param2: Description of param2 (default: 10)

    Returns:
        Dictionary with results
    """
    logger.info(f"[my_new_tool] Called with: {param1}, {param2}")

    try:
        # Tool logic here
        result = {"success": True, "data": "..."}
        return result
    except Exception as e:
        logger.error(f"[my_new_tool] Error: {e}")
        return {"success": False, "error": str(e)}
```

2. **Context-aware tools** (access BotState):

```python
from agents import function_tool, RunContextWrapper
from emailbot.core.state import BotState

@function_tool
def my_context_tool(ctx: RunContextWrapper[BotState], query: str) -> dict:
    """Tool that can access and modify BotState."""
    state = ctx.context
    user_id = state.user_context.user_id
    # ... use state ...
    # Optionally update state:
    state.user_context.some_field = "new_value"
    return {"result": "..."}
```

3. **Register the tool** in `app/tools/__init__.py`:

```python
from emailbot.tools.my_tools import my_new_tool
```

4. **Assign to agent** in the agent creator function:

```python
def create_my_agent() -> Agent:
    from emailbot.tools.my_tools import my_new_tool
    return Agent(
        ...,
        tools=[my_new_tool],
    )
```

### How to Add a New Prompt

1. Create `app/prompts/my_prompt.py`
2. Follow the `CACHE_BREAK` pattern: static content first, dynamic content second
3. Export from `app/prompts/__init__.py`
4. Use in the dynamic instruction generator

### How to Add a New API Endpoint

1. Add the endpoint in `main.py`:

```python
@app.post("/my_endpoint")
async def my_endpoint(request: MyRequest) -> MyResponse:
    # Implementation
    pass
```

2. Define request/response models in `app/core/models.py`:

```python
class MyRequest(BaseModel):
    field1: str = Field(..., description="Required field")
    field2: Optional[int] = Field(default=None)

class MyResponse(BaseModel):
    result: str
    status: str = "success"
```

---

## API Documentation

### Core Classes

#### `BotState`

The central state object passed through the entire pipeline.

```python
from emailbot.core.models import BotState

state = BotState(
    user_context=UserContext(user_id="123", user_query="Hello"),
    bot_persona=BotPersona(name="Arya", company_name="AI Sante"),
)
```

#### `AgentFactory`

Creates and caches agents.

```python
from emailbot.emailagents.factory import get_factory

factory = get_factory()
sales = factory.create_agent("sales_agent")
root = factory.create_root_agent()
```

#### `RouterModel`

LiteLLM-backed model for the Agents SDK.

```python
from emailbot.route.route import RouterModel

model = RouterModel(model="primary")   # GPT-4.1
guard = RouterModel(model="guardrail") # GPT-4o-mini
```

#### `ProbingEngine`

Manages probing question scores and completion.

```python
from emailbot.core.probing import ProbingEngine

engine = ProbingEngine(state)
probing_context, objection_state = engine.update_probing_context(probing_details)
```

#### `Settings`

Environment-based configuration.

```python
from emailbot.config.settings import settings

print(settings.primary_model)        # "gpt-4.1"
print(settings.is_production)        # False
print(settings.get_model_config())   # Dict of all model names
```

### Key Functions

| Function                              | Module                            | Purpose                         |
| ------------------------------------- | --------------------------------- | ------------------------------- |
| `run_emailbot_api(state)`             | `app_agent.py`                    | Main execution pipeline         |
| `create_root_agent()`                 | `app/agents/factory.py`           | Build complete agent tree       |
| `root_agent()`                        | `app/agents/factory.py`           | Alias for `create_root_agent()` |
| `convert_fastapi_to_botrequest(req)`  | `main.py`                         | Convert API request to BotState |
| `split_cached_prompt(instructions)`   | `app/utils/prompt_cache.py`       | Split prompt on CACHE_BREAK     |
| `retrieve_from_cache(user_id, query)` | `app/database/cachememory.py`     | Semantic cache lookup           |
| `serialize_state(state)`              | `app/database/session_manager.py` | BotState → JSON                 |
| `deserialize_to_botstate(data)`       | `app/database/session_manager.py` | JSON → BotState                 |

---

## Common Development Tasks

### Modifying Agent Behavior

1. Find the agent's dynamic instruction generator in `app/agents/definitions.py`
2. Identify which prompt module it calls (e.g., `app/prompts/sales.py`)
3. Modify the prompt template — remember to keep static content before `CACHE_BREAK`
4. Test by sending a query that triggers that agent

### Adding Fields to BotState

1. Add the field to the appropriate model in `app/core/models.py`
2. If it should be in agent output, add to `BotResponse`
3. Update `_apply_output_to_state()` in `app_agent.py` if custom mapping is needed
4. Update serialization in `session_manager.py` if using nested Pydantic models

### Changing the LLM Model

Update `.env`:

```env
PRIMARY_MODEL=gpt-4.1
GUARDRAIL_MODEL=gpt-4o-mini
SUMMARIZER_MODEL=gpt-5-nano
```

For completely new providers, add model entries to `MODEL_LIST` in `app/route/route.py`.

---

## Debugging & Troubleshooting

### Common Issues

| Issue                              | Cause                                | Solution                                                           |
| ---------------------------------- | ------------------------------------ | ------------------------------------------------------------------ |
| `AgentExecutionError`              | LLM API failure                      | Check API keys, model name, fallback configuration                 |
| `StateValidationError`             | Invalid field in BotState            | Check Pydantic model field types and validators                    |
| `InputGuardrailError`              | Input blocked by guardrail           | Check if query matches attack patterns; review guardrail prompt    |
| `OutputGuardrailTripwireTriggered` | Response blocked by output guardrail | Review output guardrail prompt and thresholds                      |
| Import errors                      | Missing dependency                   | Run `pip install -r requirements.txt`                              |
| ChromaDB collection not found      | Missing KB data                      | Ingest documents via `/ingest_documents` or verify `DATABASE_PATH` |
| Empty responses                    | Agent output parsing failure         | Check `BotResponse` schema compatibility                           |

### Debugging Techniques

**1. Enable debug logging:**

```env
DEBUG=true
ENVIRONMENT=development
```

**2. Check Opik traces:**
If `OPIK_PROJECT_NAME` is configured, all agent executions are traced in the Opik dashboard.

**3. Check prompt cache statistics:**

```bash
curl http://localhost:8000/cache_stats
```

**4. Inspect state at any point:**

```python
from emailbot.config.settings import logger
logger.debug(f"State: {state.model_dump()}")
```

**5. Test individual tools:**

```python
from emailbot.tools.booking_tools import process_booking_datetime
result = process_booking_datetime(ctx, "tomorrow at 3 PM", "America/New_York")
```

### Logging Best Practices

```python
from emailbot.config.settings import logger

# Informational (agent flow)
logger.info(f"[agent_name] Processing user_id={user_id}")

# Warnings (degraded but functional)
logger.warning(f"[cache] Cache miss for user_id={user_id}")

# Errors (failures that need attention)
logger.error(f"[tool_name] Error: {e}")
logger.exception("Full traceback:")  # Includes stack trace

# Debug (detailed state)
logger.debug(f"[state] Collected fields: {state.user_context.collected_fields}")
```

---

## Best Practices

### Agent Design

- Keep agents **focused** — each agent should have a single clear responsibility
- Use **dynamic instructions** — never hardcode prompts; generate from state
- Use **`CACHE_BREAK`** in all prompts to maximize prompt caching
- Always provide a **fallback** in dynamic instruction generators

### Tool Design

- Use **`@function_tool`** decorator for all tools
- Write **clear docstrings** — the LLM uses them to decide when to call the tool
- Return **dictionaries** with `success` flag and clear error messages
- **Log** all tool invocations and results

### State Management

- Never modify `BotState` directly in tools — use `RunContextWrapper[BotState]`
- All state changes flow through `finalize_bot_state()` in `app_agent.py`
- Use Pydantic validators for field-level validation

### Error Handling

- Use domain-specific exceptions from `app/core/exceptions.py`
- Always catch and log exceptions in tools — never let them propagate unhandled
- Provide graceful fallback responses instead of HTTP 500 errors

### Performance

- Profile prompt token usage — keep static prompt portions stable across requests
- Use the `guardrail` model (small/fast) for validation tasks
- Use the `summarizer` model for summarization tasks
- Monitor cache hit rates via `/cache_stats`

---

## Contributing Code

### Git Workflow

1. Create a feature branch from `main`: `git checkout -b feature/my-feature`
2. Make changes with descriptive commits
3. Ensure all tests pass: `python tests/comprehensive_test.py`
4. Push and open a pull request
5. Address review feedback
6. Merge after approval

### Code Review Checklist

- [ ] Code follows project naming conventions
- [ ] Pydantic models used for all data structures
- [ ] `@function_tool` decorator on all tools
- [ ] `logger` logging at appropriate levels
- [ ] `@track` decorator on key functions for Opik tracing
- [ ] Error handling with domain-specific exceptions
- [ ] Prompt uses `CACHE_BREAK` pattern
- [ ] New features are tested
- [ ] Documentation updated

### Testing Requirements

- Add tests for new tools and endpoints
- Test happy path and error scenarios
- Verify agent handoff routing
- Check guardrail behavior with edge cases

### Documentation Requirements

- Update README.md if adding new agents or endpoints
- Update ARCHITECTURE.md for structural changes
- Add docstrings to all public functions and classes
- Update `.env_example` for new configuration variables
