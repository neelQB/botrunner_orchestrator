# BotRunner Tools Reference

> **Last Updated:** February 6, 2026 &nbsp;|&nbsp; **Version:** 2.0.0

Complete reference for all tools available in the BotRunner agent framework. Tools are implemented using the `@function_tool` decorator from the OpenAI Agents SDK.

---

## Table of Contents

- [Tool Overview](#tool-overview)
- [Function Tools](#function-tools)
  - [retrieve_query](#retrieve_query)
  - [process_booking_datetime](#process_booking_datetime)
  - [check_calendly_availability](#check_calendly_availability)
  - [get_timezone](#get_timezone)
  - [process_followup_datetime](#process_followup_datetime)
  - [validate_email](#validate_email)
- [Agent-as-Tool](#agent-as-tool)
  - [lead_analysis_tool](#lead_analysis_tool)
  - [proceed_with_email](#proceed_with_email)
- [Tool Architecture](#tool-architecture)
- [Error Handling Patterns](#error-handling-patterns)

---

## Tool Overview

| Tool | Type | Module | Used By | Purpose |
|------|------|--------|---------|---------|
| `retrieve_query` | function_tool | `app/tools/sales_tools.py` | Sales Agent | RAG knowledge base search |
| `process_booking_datetime` | function_tool | `app/tools/booking_tools.py` | Demo Booking Agent | Parse & validate booking date/time |
| `check_calendly_availability` | function_tool | `app/tools/booking_tools.py` | Demo Booking Agent | Check Calendly slot availability |
| `get_timezone` | function_tool | `app/tools/followup_timezone.py` | Demo Booking, Follow-up | Resolve region to timezone |
| `process_followup_datetime` | function_tool | `app/tools/followup_timezone.py` | Follow-up Agent | Parse & validate follow-up date/time |
| `validate_email` | function_tool | `app/tools/human_tools.py` | Human Agent | Email validation & typo detection |
| `lead_analysis_tool` | Agent-as-Tool | `app/agents/definitions.py` | Demo Booking Agent | Classify lead quality |
| `proceed_with_email` | Agent-as-Tool | `app/agents/definitions.py` | Main Agent | Switch conversation to email channel |

---

## Function Tools

### retrieve_query

**File:** `app/tools/sales_tools.py`  
**Used By:** Sales Agent  
**Context Access:** Yes (`RunContextWrapper[BotState]`)

#### Purpose
Search the RAG knowledge base for documents relevant to the user's query. Supports both ChromaDB (development) and Qdrant (production) backends with multi-tenant isolation.

#### Signature

```python
@function_tool
def retrieve_query(ctx: RunContextWrapper[BotState], user_query: str) -> str
```

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `ctx` | `RunContextWrapper[BotState]` | Yes (implicit) | Agent context with BotState |
| `user_query` | `str` | Yes | The user's search query |

#### Processing

1. Extracts `user_id` from `ctx.context.user_context.user_id`
2. Generates embedding using SentenceTransformer (`all-MiniLM-L6-v2`)
3. Queries the appropriate vector DB:
   - **ChromaDB:** Collection named `user_{user_id}`, cosine similarity, top-10 results
   - **Qdrant:** Collection named `user_{user_id}`, filtered by `user_id` payload, top-10 results
4. Concatenates top document texts with metadata

#### Return Value

| Case | Returns |
|------|---------|
| Documents found | Concatenated document text from top results |
| No documents | `"No relevant documents found in the knowledge base for this user..."` |
| Error | `"Error retrieving from knowledge base: {error}"` |

#### Example

```python
# Agent calls this automatically when user asks product questions:
result = retrieve_query(ctx, "What are the pricing plans?")
# → "Document 1: Our pricing starts at...\n\nDocument 2: Enterprise plans include..."
```

#### Notes
- Collection is tenant-isolated by `user_id` — each tenant has their own KB
- Embedding model is loaded once and cached
- Returns raw document text for the agent to synthesize

---

### process_booking_datetime

**File:** `app/tools/booking_tools.py`  
**Used By:** Demo Booking Agent  
**Context Access:** Yes (`RunContextWrapper[BotState]`)

#### Purpose
Parse natural language datetime expressions into structured booking data with comprehensive validation against working hours, holidays, and time constraints.

#### Signature

```python
@function_tool
def process_booking_datetime(
    ctx: RunContextWrapper[BotState],
    user_datetime: str,
    timezone: str
) -> dict
```

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `ctx` | `RunContextWrapper[BotState]` | Yes (implicit) | Agent context |
| `user_datetime` | `str` | Yes | Natural language datetime (e.g., "tomorrow at 3 PM") |
| `timezone` | `str` | Yes | IANA timezone (e.g., "America/New_York") |

#### Processing

1. Parse natural language datetime using `dateparser` with timezone awareness
2. Validate against business rules:
   - **Not in the past** — rejects dates before current time
   - **Working days** — checks against `WorkingHours.working_days` (default: Mon–Fri)
   - **Working hours** — validates within `start_time`–`end_time` window (default: 10:00–19:00)
   - **Holiday check** — validates against `WorkingHours.holidays` list
3. Convert to UTC for Calendly API
4. Return structured result

#### Return Value

| Field | Type | Description |
|-------|------|-------------|
| `success` | `bool` | Whether parsing and validation succeeded |
| `date` | `str` | Parsed date (YYYY-MM-DD) |
| `time` | `str` | Parsed time (HH:MM) |
| `timezone` | `str` | Applied timezone |
| `utc_datetime` | `str` | UTC ISO string |
| `is_past` | `bool` | Whether the date is in the past |
| `is_holiday` | `bool` | Whether the date falls on a holiday |
| `is_outside_hours` | `bool` | Whether the time is outside working hours |
| `next_action` | `str` | Suggested action: `"confirm"`, `"ask_correction"`, `"suggest_alternative"` |
| `working_hours` | `dict` | Working hours configuration for user reference |

#### Error Cases

| Error | Returns |
|-------|---------|
| Unparseable datetime | `{"success": False, "error": "Could not parse datetime", "next_action": "ask_correction"}` |
| Past date | `{"success": False, "is_past": True, "next_action": "ask_correction"}` |
| Holiday | `{"success": False, "is_holiday": True, "holiday_name": "...", "next_action": "suggest_alternative"}` |
| Outside hours | `{"success": False, "is_outside_hours": True, "next_action": "suggest_alternative"}` |

---

### check_calendly_availability

**File:** `app/tools/booking_tools.py`  
**Used By:** Demo Booking Agent  
**Context Access:** Yes (`RunContextWrapper[BotState]`)

#### Purpose
Check real-time slot availability on Calendly for the specified date/time.

#### Signature

```python
@function_tool
def check_calendly_availability(
    ctx: RunContextWrapper[BotState],
    tenant_id: str,
    slot_datetime: str
) -> dict
```

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `ctx` | `RunContextWrapper[BotState]` | Yes (implicit) | Agent context |
| `tenant_id` | `str` | Yes | Tenant/user identifier for Calendly lookup |
| `slot_datetime` | `str` | Yes | UTC ISO datetime to check |

#### Return Value

| Field | Type | Description |
|-------|------|-------------|
| `available` | `bool` | Whether the slot is available |
| `slots` | `list` | Available time slots on that day |
| `next_available` | `str` | Next available slot if requested is taken |

#### Notes
- Calls `CalendlyAPI` under the hood (`app/apis/calendly_api.py`)
- Requires `CALENDLY_API_KEY` to be configured
- Falls back gracefully if Calendly is unreachable

---

### get_timezone

**File:** `app/tools/followup_timezone.py`  
**Used By:** Demo Booking Agent, Follow-up Agent  
**Context Access:** Yes (`RunContextWrapper[BotState]`)

#### Purpose
Resolve a country/region code to IANA timezone(s). Handles multi-timezone countries by flagging for user clarification.

#### Signature

```python
@function_tool
def get_timezone(ctx: RunContextWrapper[BotState], region_code: str) -> dict
```

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `ctx` | `RunContextWrapper[BotState]` | Yes (implicit) | Agent context |
| `region_code` | `str` | Yes | ISO country/region code (e.g., "US", "IN", "GB") |

#### Return Value

| Field | Type | Description |
|-------|------|-------------|
| `timezone` | `str` | Primary IANA timezone (e.g., "Asia/Kolkata") |
| `ismultiple_timezone` | `bool` | Whether the region has multiple timezones |
| `timezones` | `list[str]` | All timezones for multi-timezone regions |
| `country` | `str` | Resolved country name |

#### Example

```python
# Single timezone country
get_timezone(ctx, "IN")
# → {"timezone": "Asia/Kolkata", "ismultiple_timezone": False}

# Multi-timezone country
get_timezone(ctx, "US")
# → {"timezone": "America/New_York", "ismultiple_timezone": True,
#     "timezones": ["America/New_York", "America/Chicago", ...]}
```

---

### process_followup_datetime

**File:** `app/tools/followup_timezone.py`  
**Used By:** Follow-up Agent  
**Context Access:** Yes (`RunContextWrapper[BotState]`)

#### Purpose
Parse natural language datetime for follow-up scheduling with validation (not past, not >90 days future).

#### Signature

```python
@function_tool
def process_followup_datetime(
    ctx: RunContextWrapper[BotState],
    user_datetime: str,
    timezone: str
) -> dict
```

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `ctx` | `RunContextWrapper[BotState]` | Yes (implicit) | Agent context |
| `user_datetime` | `str` | Yes | Natural language datetime (e.g., "in 30 minutes", "next Monday") |
| `timezone` | `str` | Yes | IANA timezone |

#### Return Value

| Field | Type | Description |
|-------|------|-------------|
| `success` | `bool` | Whether parsing succeeded |
| `followup_time` | `str` | ISO datetime in the specified timezone |
| `utc_time` | `str` | UTC equivalent |
| `human_readable` | `str` | Formatted string for display |
| `is_past` | `bool` | Whether the time is in the past |
| `too_far_future` | `bool` | Whether >90 days in the future |

#### Notes
- Supports relative expressions: "in 30 minutes", "in 2 hours"
- Supports named days: "next Monday", "this Friday"
- Supports absolute dates: "March 15 at 2 PM"
- 90-day maximum future window

---

### validate_email

**File:** `app/tools/human_tools.py`  
**Used By:** Human Agent  
**Context Access:** Yes (`RunContextWrapper[BotState]`)

#### Purpose
Validate email addresses with format checking and common typo detection (e.g., "gmial.com" → "gmail.com").

#### Signature

```python
@function_tool
def validate_email(ctx: RunContextWrapper[BotState], email: str) -> dict
```

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `ctx` | `RunContextWrapper[BotState]` | Yes (implicit) | Agent context |
| `email` | `str` | Yes | Email address to validate |

#### Return Value

| Field | Type | Description |
|-------|------|-------------|
| `is_valid` | `bool` | Whether the email is valid |
| `typo_detected` | `bool` | Whether a common typo was found |
| `suggestion` | `str` | Suggested correction (if typo detected) |
| `domain` | `str` | Extracted domain |
| `error` | `str` | Error description (if invalid) |

#### Example

```python
validate_email(ctx, "john@gmial.com")
# → {"is_valid": False, "typo_detected": True, "suggestion": "john@gmail.com"}

validate_email(ctx, "john@gmail.com")
# → {"is_valid": True, "typo_detected": False}
```

---

## Agent-as-Tool

These tools are implemented as OpenAI Agents SDK `Agent` instances used as tools by other agents. They run a full agent execution internally.

### lead_analysis_tool

**Defined In:** `app/agents/definitions.py` → `create_lead_analysis_agent()`  
**Used By:** Demo Booking Agent  
**Type:** Agent with `tool_use_behavior="run_llm"`

#### Purpose
Classify the lead quality based on conversation history, engagement level, and collected information.

#### Input
The agent receives the full conversation context from the parent agent.

#### Output: `LeadAnalysis`

| Field | Type | Description |
|-------|------|-------------|
| `lead_classification` | `LeadClassification` | `hot`, `warm`, `cold`, `unqualified` |
| `reasoning` | `str` | Explanation of classification |
| `key_indicators` | `list[str]` | Signals that influenced the classification |
| `urgency_level` | `UrgencyLevel` | `immediate`, `short_term`, `long_term`, `none` |
| `recommended_next_action` | `str` | Suggested follow-up action |

#### Classification Criteria

| Classification | Indicators |
|---------------|------------|
| `hot` | Immediate need, budget confirmed, quick decision, booked demo |
| `warm` | Interest shown, questions asked, exploring options |
| `cold` | Low engagement, no urgency, information gathering only |
| `unqualified` | Wrong fit, no authority, no budget, no need |

---

### proceed_with_email

**Defined In:** `app/agents/definitions.py` → `create_proceed_email_agent()`  
**Used By:** Main Agent  
**Type:** Agent with `tool_use_behavior="run_llm"`

#### Purpose
Handle transition from live chat to email communication when the user prefers email.

#### Output: `ProceedEmailDetails`

| Field | Type | Description |
|-------|------|-------------|
| `switch_to_email` | `bool` | Whether to switch to email |
| `get_email_flag` | `bool` | Whether to prompt for email address |

---

## Tool Architecture

### Context Flow

```
Agent (instructions + user message)
  ↓
Tool called by LLM
  ↓
RunContextWrapper[BotState] injected automatically
  ↓
Tool accesses state: ctx.context
  ↓
Tool can read/write BotState fields
  ↓
Result returned to agent as string/dict
  ↓
Agent incorporates tool result into response
```

### Tool Registration

Tools are registered in agent definitions:

```python
# In emailbot/emailagents/definitions.py
def create_demo_booking_agent():
    return Agent(
        name="demo_booking_agent",
        tools=[
            get_timezone,
            process_booking_datetime,
            check_calendly_availability,
            lead_analysis_tool,  # Agent-as-tool
        ],
        ...
    )
```

### Error Handling Patterns

All tools follow a consistent error handling pattern:

```python
@function_tool
def my_tool(ctx: RunContextWrapper[BotState], param: str) -> dict:
    try:
        # Tool logic
        return {"success": True, "data": result}
    except SpecificError as e:
        logger.error(f"[my_tool] Specific error: {e}")
        return {"success": False, "error": str(e), "next_action": "retry"}
    except Exception as e:
        logger.exception(f"[my_tool] Unexpected error: {e}")
        return {"success": False, "error": "An unexpected error occurred"}
```

**Principles:**
- Tools never raise unhandled exceptions to the agent
- All errors return structured dicts with `success: False`
- `next_action` field guides the agent on how to respond
- All tool calls are logged with `logger`
- Opik `@track` decorator provides observability

---

*For related documentation, see:*
- [AGENT_FLOWS.md](AGENT_FLOWS.md) — How tools are used in agent workflows
- [DEVELOPERS.md](DEVELOPERS.md) — How to create new tools
- [ARCHITECTURE.md](ARCHITECTURE.md) — System architecture
