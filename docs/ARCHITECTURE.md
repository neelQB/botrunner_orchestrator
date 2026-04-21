# BotRunner Architecture Documentation

> **Last Updated:** February 6, 2026 &nbsp;|&nbsp; **Version:** 2.0.0

---

## Table of Contents

- [Overview](#overview)
- [System Architecture](#system-architecture)
- [Component Breakdown](#component-breakdown)
  - [API Layer](#1-api-layer)
  - [Application Layer](#2-application-layer)
  - [Agent System](#3-agent-system)
  - [Tools & Integrations](#4-tools--integrations)
  - [Data Layer](#5-data-layer)
- [Design Patterns](#design-patterns)
- [Data Models](#data-models)
- [Technology Stack](#technology-stack)
- [LLM Routing & Fallback](#llm-routing--fallback)
- [Guardrail Architecture](#guardrail-architecture)
- [Prompt Caching Strategy](#prompt-caching-strategy)
- [Session & State Management](#session--state-management)

---

## Overview

BotRunner is a production-ready multi-agent chatbot system built on the **OpenAI Agents SDK v0.6.1**. It provides intelligent sales and support automation with:

- **Multi-Agent Orchestration** — 7+ specialized agents with handoff capabilities
- **RAG Integration** — Dual vector database support (ChromaDB/Qdrant)
- **Guardrails** — Input and output validation for safety and quality
- **Session Management** — Persistent conversations with semantic caching
- **Dynamic Probing** — Intelligent question generation for lead qualification
- **Multi-Model Fallback** — Automatic failover across OpenAI, Azure, and Gemini

---

## System Architecture

### High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           API Layer (FastAPI)                                │
│   POST /chat          POST /chat_ui         POST /autofill_persona          │
│   POST /generate_probing_questions          POST /ingest_documents          │
│   POST /generate_instructions               GET  /health                    │
│   GET  /cache_stats   POST /cache_stats/reset                               │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
                    ┌─────────────────┼──────────────────┐
                    │                 │                   │
                    ▼                 ▼                   ▼
        ┌───────────────────┐ ┌──────────────┐ ┌──────────────────┐
        │ Request Conversion│ │  Standalone   │ │  Document        │
        │ (BotRequest →     │ │  Agents       │ │  Ingestion       │
        │  BotState)        │ │  (Probing,    │ │  (ChromaDB)      │
        │                   │ │  Crawl)       │ │                  │
        └────────┬──────────┘ └──────────────┘ └──────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Application Layer (app_agent.py)                     │
│                                                                              │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                  │
│   │ Session Init  │───▶│ Cache Lookup │───▶│Agent Execute │                  │
│   │ (DB + Memory) │    │ (Semantic)   │    │  (Runner)    │                  │
│   └──────────────┘    └──────────────┘    └──────┬───────┘                  │
│                                                   │                          │
│   ┌──────────────┐    ┌──────────────┐    ┌──────▼───────┐                  │
│   │  DB Save     │◀───│ Summarize    │◀───│  Finalize    │                  │
│   │  (State)     │    │ (Chat + Exec)│    │  (State)     │                  │
│   └──────────────┘    └──────────────┘    └──────────────┘                  │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Agent System                                    │
│                                                                              │
│   ┌────────────────────────────────────────────────────────────────────┐    │
│   │                    Root Agent (main_agent)                          │    │
│   │  Model: primary (GPT-4.1)                                          │    │
│   │  Input Guardrails: [input_attack]                                  │    │
│   │  Output Guardrails: [output_guardrail]                             │    │
│   │  Tools: [proceed_with_email (agent-as-tool)]                       │    │
│   │  Handoffs: [sales, demo_booking, followup, human]                  │    │
│   └──┬─────────┬──────────┬──────────┬─────────────┬───────────────────┘    │
│      │         │          │          │             │                         │
│      ▼         ▼          ▼          ▼             ▼                         │
│  ┌────────┐┌────────┐┌────────┐┌──────────┐┌──────────────┐                │
│  │ Sales  ││  Demo  ││Follow  ││  Human   ││  Proceed     │                │
│  │ Agent  ││Booking ││-up     ││  Agent   ││  Email Agent │                │
│  │        ││ Agent  ││ Agent  ││          ││              │                │
│  │Tools:  ││Tools:  ││Tools:  ││Tools:    ││Tools: none   │                │
│  │retrieve││timezone││timezone││validate  ││              │                │
│  │_query  ││datetime││followup││_email    ││              │                │
│  │        ││calendly││datetime││          ││              │                │
│  │        ││lead_   ││        ││          ││              │                │
│  │        ││analysis││        ││          ││              │                │
│  └────────┘└───┬────┘└────────┘└──────────┘└──────────────┘                │
│                │                                                             │
│                ▼                                                             │
│         ┌─────────────┐                                                     │
│         │Lead Analysis│  (Agent used as tool by Demo Booking)               │
│         │Agent        │                                                     │
│         └─────────────┘                                                     │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          LLM Routing (LiteLLM)                               │
│                                                                              │
│   ┌──────────────┐     ┌──────────────┐     ┌──────────────────┐            │
│   │  Primary      │────▶│  Azure       │────▶│  Gemini          │            │
│   │  GPT-4.1     │ fail│  GPT-4.1     │ fail│  3 Flash Preview │            │
│   └──────────────┘     └──────────────┘     └──────────────────┘            │
│                                                                              │
│   Models: primary │ fallback │ fallback-gemini │ guardrail │ summarizer     │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            Data Layer                                        │
│                                                                              │
│   ┌──────────────────┐  ┌──────────────────┐  ┌───────────────────────┐     │
│   │  SQLite / Neon   │  │  ChromaDB/Qdrant │  │   Semantic Cache      │     │
│   │  PostgreSQL      │  │  (Vector Store)  │  │   (In-Memory +        │     │
│   │  (Session State) │  │  (Knowledge Base)│  │    SentenceTransformer│     │
│   └──────────────────┘  └──────────────────┘  └───────────────────────┘     │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Component Breakdown

### 1. API Layer

**File:** `main.py`

The FastAPI application provides all HTTP endpoints. Key responsibilities:

| Endpoint                           | Handler                                    | Flow                                                                                    |
| ---------------------------------- | ------------------------------------------ | --------------------------------------------------------------------------------------- |
| `POST /chat`                       | `chat_endpoint()`                          | `BotRequest` → `convert_fastapi_to_botrequest()` → `run_emailbot_api()` → `APIResponse` |
| `POST /chat_ui`                    | `chat_streamlit()`                         | Same as `/chat` but returns full `BotState` dict                                        |
| `POST /generate_probing_questions` | `generate_probing_questions()`             | `ProbingRequest` → `run_probing_agent()` → questions list                               |
| `POST /autofill_persona`           | `autofill_persona()`                       | `AutofillPersonaRequest` → `run_crawl_persona_agent()` → persona dict                   |
| `POST /ingest_documents`           | `ingest_documents_endpoint()`              | Upload file → `ingest_text_file()` → ChromaDB                                           |
| `POST /generate_instructions`      | `generate_probing_instructions_endpoint()` | `InstructionAgentRequest` → instructions list                                           |

**Request conversion** in `convert_fastapi_to_botrequest()`:

- Gets or creates session state from database
- Merges meaningful fields from the request into existing state
- Handles nested Pydantic model merging (contact details, collected fields, etc.)

### 2. Application Layer

**File:** `app_agent.py`

The central execution engine that orchestrates the entire chatbot pipeline:

```
run_emailbot_api(state: BotState)
  ├── _initialize_session(state, user_id, chat_history)
  │     ├── init_session(user_id)          # Semantic cache
  │     ├── sessions[user_id].add_items()  # Summarizer session
  │     └── Restore chat summary from state
  │
  ├── _retrieve_cached_pairs(user_id, user_query)
  │     └── retrieve_from_cache()          # Embedding similarity search
  │
  ├── _build_agent_input(state, user_query)
  │     └── Combine chat history + new query as messages
  │
  ├── _execute_agent(state, agent_input)
  │     ├── root_agent()                   # Create agent tree
  │     └── Runner.run()                   # OpenAI Agents SDK execution
  │
  ├── finalize_bot_state(state, result, user_query)
  │     ├── _extract_output_data()         # Parse agent output
  │     ├── _apply_output_to_state()       # Merge results into BotState
  │     ├── _update_chat_history()         # Append to history
  │     ├── _update_chat_summary()         # Trigger summarization
  │     ├── _update_executive_summary()    # Milestone summaries
  │     └── _update_probing_context()      # Score tracking
  │
  ├── save_state(user_id, state)           # Persist to DB
  └── update_session()                     # Update semantic cache
```

### 3. Agent System

#### Agent Hierarchy

All agents are defined in `app/agents/definitions.py` and created via `app/agents/factory.py`.

**Root Agent (main_agent)**

- **Type:** `Agent[BotState]`
- **Instructions:** `dynamic_main_instructions()` — generates context-aware triage prompt
- **Input Guardrails:** `[input_attack]`
- **Output Guardrails:** `[output_guardrail]`
- **Tools:** `[proceed_with_email]` (Proceed Email Agent as tool)
- **Handoffs:** Sales → Demo Booking → Follow-up → Human (each with callback)

**Sales Agent (sales_agent)**

- **Instructions:** `dynamic_sales_instructions()` — persona + products + RAG context
- **Tools:** `[retrieve_query]` — RAG knowledge base search
- **Output Type:** `BotResponse`

**Demo Booking Agent (demo_booking_agent)**

- **Instructions:** `dynamic_demo_instructions()` — booking state + collected fields
- **Tools:** `[get_timezone, process_booking_datetime, check_calendly_availability, lead_analysis_tool]`
- **Capabilities:** New booking, rescheduling, cancellation, lead analysis post-booking

**Follow-up Agent (followup_agent)**

- **Instructions:** `dynamic_followup_instructions()`
- **Tools:** `[get_timezone, process_followup_datetime]`
- **Handles:** Relative time expressions ("in 30 minutes", "next Monday at 3 PM")

**Human Agent (human_agent)**

- **Instructions:** `dynamic_human_instructions()`
- **Tools:** `[validate_email]`
- **Output Guardrails:** `[output_guardrail]`

**Proceed Email Agent (switch_to_email_agent)**

- **Instructions:** `dynamic_proceed_with_email_instructions()`
- **Used as tool** by the Root Agent (not a handoff target)

**Lead Analysis Agent (lead_analysis_agent)**

- **Instructions:** Static `lead_analysis_prompt`
- **Used as tool** by the Demo Booking Agent post-booking confirmation

#### AgentFactory Pattern

```python
class AgentFactory:
    _cache: Dict[str, Agent]          # Singleton cache
    _creators: Dict[str, Callable]    # Name → creator function mapping

    def create_agent(name, use_cache=True) → Agent
    def create_root_agent() → Agent   # Full agent tree
    def register_creator(name, fn)    # Extensibility
```

The `AgentFactory` uses a dictionary of creator functions and an internal cache to ensure each agent type is instantiated only once per application lifecycle.

#### Handoff Callbacks

Defined in `app/callbacks/handlers.py`:

| Callback              | Trigger                 | State Changes                                              |
| --------------------- | ----------------------- | ---------------------------------------------------------- |
| `on_sales_handoff`    | Handoff to sales        | `new_booking = True`                                       |
| `on_demo_handoff`     | Handoff to demo booking | `new_booking = True`                                       |
| `on_followup_handoff` | Handoff to follow-up    | `follow_trigger = True`                                    |
| `on_human_handoff`    | Handoff to human        | `human_requested = True`, `escalation_timestamp = UTC now` |

All callbacks are decorated with `@track` for Opik tracing.

### 4. Tools & Integrations

#### RAG Retrieval — `retrieve_query`

```
User Query → SentenceTransformer Embedding → Vector DB Query → Top-10 Documents
```

- **ChromaDB:** Uses `all-mpnet-base-v2` embeddings, persistent client, tenant-isolated collections
- **Qdrant:** Uses custom `Retriever` class with advanced embedding and reranking
- **Tenant isolation:** `get_current_user_id()` provides the collection name via `contextvars`
- **Graceful fallback:** Returns persona-based response if KB unavailable

#### Datetime Processing — `process_booking_datetime`

Unified tool that combines:

1. **Parsing** — handles natural language ("tomorrow at 3 PM", "next Monday", "in 30 minutes")
2. **Validation** — checks business hours (`WorkingHours` model), past dates, too-far-future
3. **UTC Conversion** — converts local time to UTC using `pytz`

Supports: relative time, day names, explicit dates, AM/PM, 24h format, time-of-day references.

#### Calendly Integration — `check_calendly_availability`

- Queries Calendly API for available 30-minute meeting slots
- Rounds to nearest 30-minute boundary
- Returns up to 5 slots per query with 7-day lookahead
- Currently uses mocked response for demo; production code is commented but complete

#### Email Validation — `validate_email`

- Regex-based format validation
- **Typo detection** — maps 20+ common domain typos (gamil.com → gmail.com, etc.)
- Suspicious pattern detection (double dots, leading dots, etc.)
- Returns validation result with suggested corrections

### 5. Data Layer

#### Session Management (`app/database/session_manager.py`)

Abstract `SessionManagerBase` with two implementations:

| Feature          | SQLiteSessionManager                       | NeonSessionManager          |
| ---------------- | ------------------------------------------ | --------------------------- |
| Storage          | Local SQLite file (`data/chat_history.db`) | Neon PostgreSQL (cloud)     |
| Serialization    | JSON via `PydanticEncoder`                 | JSON via `PydanticEncoder`  |
| Deserialization  | `deserialize_to_botstate()`                | `deserialize_to_botstate()` |
| Session Creation | Creates default `BotState`                 | Creates default `BotState`  |

#### Semantic Cache (`app/database/cachememory.py`)

- **In-memory** per-user Q/A pair cache (max 15 pairs)
- **Embedding model:** `"text-embedding-3-small"`
- **Similarity:** Cosine similarity with configurable threshold (default 0.5)
- **Returns:** Top-K most similar cached Q/A pairs for context enrichment

#### Progressive Summarization (`app/database/summarizer.py`)

`SummarizingSession` class:

- Tracks user turns and triggers summarization when count exceeds `context_limit`
- Keeps last N turns verbatim, summarizes everything before
- Uses `LLMSummarizer` with the `summarizer` model
- Thread-safe with `asyncio.Lock`

#### Executive Summary (`app/database/executive_summary.py`)

Triggered by:

1. Booking confirmed + lead details generated
2. Chat history crosses 15-message milestones

Uses HTML-like markers (e.g., `<!-- demo_booked -->`, `<!-- milestone: 15 -->`) to track generation state within the summary text itself.

---

## Design Patterns

### 1. Factory Pattern (Agent Creation)

`AgentFactory` centralizes agent creation with caching, extensibility via `register_creator()`, and consistent configuration.

### 2. Strategy Pattern (LLM Routing)

`RouterModel` extends `LitellmModel` to inject LiteLLM Router's multi-model fallback into the OpenAI Agents SDK's model interface.

### 3. Observer Pattern (Handoff Callbacks)

Callbacks registered via `handoff(agent=..., on_handoff=...)` observe agent transitions and modify state.

### 4. Builder Pattern (Dynamic Instructions)

`InstructionBuilder` in `app/instructions/generators.py` constructs prompts by composing persona, context, history, and rules.

### 5. Template Method (Prompt Generation)

Each prompt module (18 total in `app/prompts/`) follows a consistent pattern: accept `BotState`, extract relevant fields, compose a formatted prompt string with `CACHE_BREAK` marker.

### 6. Context Variables (Request Scoping)

`app/core/request_context.py` uses Python's `contextvars.ContextVar` to pass the current user/tenant ID to tools without modifying function signatures.

### 7. Abstract Base Classes

`SessionManagerBase`, `BaseAgent`, `BaseInstructionBuilder` — define interfaces for extensibility.

### 8. Singleton (Settings)

`get_settings()` with `@lru_cache()` ensures a single `Settings` instance throughout the application lifecycle.

---

## Data Models

### Core Models (defined in `app/core/models.py`)

```
BotState
├── user_context: UserContext
│   ├── user_id, user_query, tenant_id
│   ├── chat_history: List[Dict]
│   ├── chat_summary, executive_summary
│   ├── contact_details: ContactDetails
│   │   └── name, email, phone, date, time, product, booking_type
│   ├── lead_details: LeadAnalysis
│   │   └── lead_classification, reasoning, key_indicators, urgency_level
│   ├── collected_fields: Dict
│   ├── followup_details: FollowupDetails
│   ├── probing_details: ProbingOutput
│   └── ... (flags: booking_confirmed, human_requested, etc.)
│
├── bot_persona: BotPersona
│   ├── name, company_name, company_domain, company_description
│   ├── company_products: List[Products]
│   ├── core_usps, core_features, contact_info
│   ├── personality, business_focus, goal_type
│   ├── rules: List[str]
│   ├── probing_questions: List[ProbingQuestion]
│   ├── probing_threshold, objection_count_limit
│   ├── working_hours: List[WorkingHours]
│   └── company_management: List[Management]
│
├── probing_context: ProbingContext
│   └── detected_question_answer, total_score, probing_completed, can_show_cta
│
├── objection_state: ObjectionState
│   └── current_objection_count, is_objection_limit_reached
│
├── input_guardrail_decision: InputGuardrail
├── response: str
├── session_id, conversation_id
```

### API Models

| Model                     | Purpose                                                                  |
| ------------------------- | ------------------------------------------------------------------------ |
| `BotRequest`              | API input: `UserContextRequest` + optional `BotPersona`                  |
| `APIResponse`             | API output: response, user_id, chat_history, summaries                   |
| `BotResponse`             | Agent output schema: response + all collected fields + guardrail results |
| `ProbingRequest`          | Probing question generation input                                        |
| `AutofillPersonaRequest`  | Website crawl + persona generation input                                 |
| `InstructionAgentRequest` | Instruction generation input                                             |

### Enumerations

| Enum                   | Values                                                                                                                                                                                                 |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `AgentName`            | `main_agent`, `sales_agent`, `demo_booking_agent`, `followup_agent`, `human_agent`, `switch_to_email_agent`, `lead_analysis_agent`, `probing_agent`, `input_guardrail_agent`, `output_guardrail_agent` |
| `BookingType`          | `new`, `reschedule`, `cancel`                                                                                                                                                                          |
| `LeadClassification`   | `hot`, `warm`, `cold`                                                                                                                                                                                  |
| `UrgencyLevel`         | `immediate`, `soon`, `later`, `no-interest`                                                                                                                                                            |
| `AttackClassification` | `prompt_injection`, `jailbreak`, `data_extraction`, `harmful_content`, `off_topic`, `none`                                                                                                             |
| `DatabaseType`         | `sqlite`, `neon`, `postgres`                                                                                                                                                                           |
| `VectorDBType`         | `chromadb`, `qdrant`                                                                                                                                                                                   |

---

## Technology Stack

| Category             | Technology               | Purpose                                |
| -------------------- | ------------------------ | -------------------------------------- |
| **Agent Framework**  | OpenAI Agents SDK v0.6.1 | Agent orchestration, handoffs, tools   |
| **API Framework**    | FastAPI                  | HTTP API server                        |
| **LLM Routing**      | LiteLLM                  | Multi-model routing and fallback       |
| **Data Validation**  | Pydantic v2              | Models, settings, serialization        |
| **Databases**        | SQLite, Neon PostgreSQL  | Session state persistence              |
| **Vector Databases** | ChromaDB, Qdrant         | RAG knowledge base                     |
| **Embeddings**       | SentenceTransformers     | Semantic caching + ChromaDB embeddings |
| **Web Crawling**     | Crawl4AI                 | Website content extraction             |
| **Observability**    | Opik                     | Tracing, monitoring                    |
| **Logging**          | logger                   | Structured logging                     |
| **Scheduling**       | Calendly API             | Demo booking integration               |
| **UI**               | Streamlit                | Admin interface                        |
| **Environment**      | pydantic-settings        | Configuration management               |

---

## LLM Routing & Fallback

Defined in `app/route/route.py`:

### Model Roles

| Role              | Default Model                   | Purpose                                 |
| ----------------- | ------------------------------- | --------------------------------------- |
| `primary`         | `gpt-4.1`/`gpt-5.1-chat-latest` | Main conversational agent               |
| `guardrail`       | `gpt-4o-mini`                   | Fast input/output validation            |
| `summarizer`      | `gpt-5-nano`                    | Chat summarization, executive summaries |
| `fallback`        | `azure/gpt-4.1`                 | First fallback (Azure)                  |
| `fallback-gemini` | `gemini/gemini-3-flash-preview` | Second fallback (Gemini)                |

### Fallback Chain

```
primary ──fail──▶ fallback (Azure) ──fail──▶ fallback-gemini (Gemini)
guardrail ──fail──▶ fallback (Azure) ──fail──▶ fallback-gemini
summarizer ──fail──▶ fallback (Azure) ──fail──▶ fallback-gemini
```

### RouterModel

`RouterModel` extends `LitellmModel` to use the global LiteLLM `Router` instance instead of direct `litellm.acompletion`. It also handles:

- Prompt prefix caching (splitting system messages on `CACHE_BREAK`)
- GPT-5 family detection for `reasoning_effort` parameter
- Tool and handoff conversion to OpenAI format

---

## Guardrail Architecture

### Input Guardrail

**File:** `app/core/guardrail.py`

```
User Message
    │
    ▼
Fast Pattern Check (SAFE_CONVERSATIONAL_PATTERNS)
    │ match → PASS (no LLM call)
    │ no match ↓
    ▼
LLM Classification (guardrail model)
    │ → InputGuardrail { is_attack_query, reason, classification }
    │
    ├── safe → PASS
    └── attack → BLOCK (GuardrailFunctionOutput with tripwire_triggered=True)
```

Safe patterns include ~50 conversational fillers (greetings, acknowledgments, thinking sounds) that bypass the LLM entirely.

### Output Guardrail

Validates agent responses for:

- Response relevance to the conversation
- Factual accuracy (RAG grounding)
- Tone alignment with persona
- Policy compliance (rules from `BotPersona`)
- PII detection

---

## Prompt Caching Strategy

**File:** `app/utils/prompt_cache.py`

OpenAI automatically caches prompt prefixes ≥ 1024 tokens at 50% input cost.

### Strategy

1. Each prompt template inserts `CACHE_BREAK` between static and dynamic content
2. `RouterModel._fetch_response()` splits on `CACHE_BREAK` into two system messages
3. Message 1 (static): role definition, rules, output format → **cached by OpenAI**
4. Message 2 (dynamic): user query, chat history, session state → **not cached**

### Monitoring

`PromptCacheMonitor` tracks:

- Total requests per model
- Cached vs. uncached input tokens
- Cache hit rate percentage
- Estimated cost savings percentage

---

## Session & State Management

### Lifecycle

```
1. Request arrives at /chat
2. convert_fastapi_to_botrequest() → merge request into existing session state
3. run_emailbot_api(state):
   a. _initialize_session() → init semantic cache + summarizer session
   b. _retrieve_cached_pairs() → find similar past Q/A pairs
   c. _build_agent_input() → construct message list
   d. _execute_agent() → Runner.run() with root agent
   e. finalize_bot_state() → extract output, update history, summaries, probing
   f. save_state() → persist to SQLite/Neon
   g. update_session() → update semantic cache
4. Return APIResponse
```

### Multi-Tenant Isolation

- **Session state:** Isolated by `user_id` (primary key in session table)
- **Vector store:** Isolated by `tenant_id` (ChromaDB collection name / Qdrant tenant)
- **Request context:** `contextvars.ContextVar` carries tenant ID to tools

---

_For more information, see the companion documentation:_

- [DEVELOPERS.md](DEVELOPERS.md) — Development setup and workflows
- [AGENT_FLOWS.md](AGENT_FLOWS.md) — Detailed agent interaction flows
- [TOOLS_REFERENCE.md](TOOLS_REFERENCE.md) — Complete tools reference
