# BotRunner Product Features

> **Last Updated:** February 6, 2026 &nbsp;|&nbsp; **Version:** 2.0.0

Comprehensive catalog of all features available in the BotRunner multi-agent framework, organized by category.

---

## Table of Contents

- [Feature Summary Matrix](#feature-summary-matrix)
- [Conversational AI Engine](#conversational-ai-engine)
- [Multi-Agent Orchestration](#multi-agent-orchestration)
- [RAG Knowledge Base](#rag-knowledge-base)
- [Demo Booking & Calendar](#demo-booking--calendar)
- [Lead Qualification & Probing](#lead-qualification--probing)
- [Persona & Customization](#persona--customization)
- [Smart Communication](#smart-communication)
- [Safety & Guardrails](#safety--guardrails)
- [Performance & Caching](#performance--caching)
- [Analytics & Observability](#analytics--observability)
- [Multi-Tenancy & Data Isolation](#multi-tenancy--data-isolation)
- [Integration Capabilities](#integration-capabilities)

---

## Feature Summary Matrix

| Category | Feature | Status | Environment |
|----------|---------|--------|-------------|
| **AI Engine** | Multi-model LLM routing | ✅ Production | All |
| **AI Engine** | 3-tier model fallback | ✅ Production | All |
| **AI Engine** | Prompt caching (OpenAI prefix caching) | ✅ Production | All |
| **AI Engine** | Semantic response caching | ✅ Production | All |
| **AI Engine** | Conversation summarization | ✅ Production | All |
| **Agents** | 7-agent orchestration graph | ✅ Production | All |
| **Agents** | Automatic agent handoffs | ✅ Production | All |
| **Agents** | Dynamic instruction generation | ✅ Production | All |
| **Agents** | Agent-as-Tool pattern | ✅ Production | All |
| **RAG** | Document ingestion API | ✅ Production | All |
| **RAG** | ChromaDB vector search | ✅ Production | Dev |
| **RAG** | Qdrant vector search | ✅ Production | Prod |
| **RAG** | Tenant-isolated collections | ✅ Production | All |
| **Booking** | Natural language date parsing | ✅ Production | All |
| **Booking** | Calendly availability check | ✅ Production | All |
| **Booking** | Working hours validation | ✅ Production | All |
| **Booking** | Reschedule/cancel flows | ✅ Production | All |
| **Probing** | Configurable qualifying questions | ✅ Production | All |
| **Probing** | Score tracking & threshold | ✅ Production | All |
| **Probing** | Objection handling | ✅ Production | All |
| **Probing** | Auto CTA trigger | ✅ Production | All |
| **Persona** | Website auto-fill (Crawl4AI) | ✅ Production | All |
| **Persona** | Configurable bot personality | ✅ Production | All |
| **Safety** | Input guardrail (attack detection) | ✅ Production | All |
| **Safety** | Output guardrail (response validation) | ✅ Production | All |
| **Safety** | Safe pattern bypass (no LLM call) | ✅ Production | All |
| **Cache** | OpenAI prompt prefix caching | ✅ Production | All |
| **Cache** | Semantic similarity cache | ✅ Production | All |
| **Cache** | Cache monitoring & stats | ✅ Production | All |
| **Analytics** | Opik tracing integration | ✅ Production | All |
| **Analytics** | Executive summary generation | ✅ Production | All |
| **Analytics** | Lead classification | ✅ Production | All |
| **Multi-Tenant** | Per-tenant KB isolation | ✅ Production | All |
| **Multi-Tenant** | Per-session state management | ✅ Production | All |
| **Integration** | FastAPI REST API | ✅ Production | All |
| **Integration** | Streamlit chat UI | ✅ Production | All |
| **Integration** | Calendly API | ✅ Production | All |

---

## Conversational AI Engine

### Multi-Model LLM Routing
BotRunner uses LiteLLM Router to direct different types of tasks to the most appropriate model:

| Model Role | Default Model | Purpose |
|------------|--------------|---------|
| `primary` | GPT-4.1 | Main agent conversations |
| `guardrail` | GPT-4o-mini | Fast input/output validation |
| `summarizer` | GPT-4o-mini | Conversation summarization |
| `fallback` | Azure GPT-4.1 | Primary failure fallback |
| `fallback-gemini` | Gemini 3 Flash | Second-tier fallback |

**3-Tier Fallback Chain:**
```
Request → GPT-4.1 (primary)
            ↓ (failure)
          Azure GPT-4.1 (fallback)
            ↓ (failure)
          Gemini 3 Flash (fallback-gemini)
```

### Prompt Caching (OpenAI Prefix Caching)
- System messages are split at `CACHE_BREAK` marker
- Static portions are sent as the first system message (cacheable)
- Dynamic/per-request portions are sent as a second system message
- Reduces latency and cost on subsequent requests with identical prompt prefixes
- `PromptCacheMonitor` tracks hit/miss rates via `/cache_stats` endpoint

### Semantic Response Caching
- In-memory cache using SentenceTransformer (`all-MiniLM-L6-v2`) embeddings
- Incoming queries are compared against cached query embeddings via cosine similarity
- If similarity exceeds threshold → cached response returned instantly (no LLM call)
- Per-user cache isolation

### Conversation Summarization
- `SummarizingSession` compresses conversation history when it exceeds `MAX_HISTORY` tokens
- Preserves key context (contact details, booking info, lead classification) in summary
- Prevents token window overflow during long conversations

---

## Multi-Agent Orchestration

### 7-Agent Handoff Graph

| Agent | Role | Handoff From | Tools |
|-------|------|-------------|-------|
| **Main (Triage)** | Intent classification, routing | Entry point | `proceed_with_email` |
| **Sales** | Product info, pricing, features | Main | `retrieve_query` |
| **Demo Booking** | Book/reschedule/cancel demos | Main | 4 tools (datetime, Calendly, timezone, lead analysis) |
| **Follow-up** | Schedule future contact | Main | `get_timezone`, `process_followup_datetime` |
| **Human** | Escalation to live support | Main | `validate_email` |
| **Lead Analysis** | Classify lead quality | Demo Booking (as tool) | — |
| **Proceed Email** | Switch to email channel | Main (as tool) | — |

### Dynamic Instruction Generation
- Each agent's instructions are generated at runtime from `BotState`
- Prompt includes persona, user context, chat summary, and collected fields
- Enables fully contextual responses without re-training

### Agent-as-Tool Pattern
- `lead_analysis_tool` and `proceed_with_email` are agents wrapped as tools
- Called by parent agents like regular functions
- Full LLM execution happens inside the tool call

---

## RAG Knowledge Base

### Document Ingestion
- **API:** `POST /ingest_documents`
- Accepts text documents with metadata
- Chunks documents, generates embeddings
- Stores in ChromaDB (dev) or Qdrant (prod)

### Vector Search
- Top-10 cosine similarity search
- SentenceTransformer `all-MiniLM-L6-v2` embeddings (384 dimensions)
- Tenant-isolated collections: `user_{user_id}`

### Supported Backends

| Backend | Use Case | Collection Isolation | Persistence |
|---------|----------|---------------------|-------------|
| ChromaDB | Development | Collection per tenant | Local disk |
| Qdrant | Production | Collection per tenant + payload filter | Persistent |

---

## Demo Booking & Calendar

### Natural Language Date Parsing
- Understands: "tomorrow at 3 PM", "next Monday", "Feb 15 at 2:30 PM"
- Timezone-aware parsing with automatic UTC conversion
- Handles relative dates: "in 2 hours", "next week"

### Business Rule Validation
- **Working hours:** Configurable start/end times (default 10:00–19:00)
- **Working days:** Configurable (default Monday–Friday)
- **Holiday calendar:** Configurable holiday list
- **Past date rejection:** Automatic with user-friendly messaging

### Calendly Integration
- Real-time availability checking via Calendly API
- Slot suggestion when requested time is unavailable
- Support for event type matching

### Booking Lifecycle
- **New booking:** Collect info → validate → check availability → confirm
- **Reschedule:** Load existing → new datetime → validate → update
- **Cancel:** Confirm cancellation → offer reschedule option

---

## Lead Qualification & Probing

### Configurable Probing System
- Admin defines qualifying questions via `POST /generate_probing_questions`
- Each question has: weight score, priority, mandatory flag
- Questions are woven naturally into conversation by agents

### Score-Based Progression
- Each answered question adds score points
- When total score ≥ threshold → `probing_completed=True`
- CTA (Call-to-Action) triggered automatically: "Would you like a demo?"

### Objection Handling
- User objections detected automatically
- Objection count tracked per session
- After reaching limit (default: 3) → probing stops gracefully
- Agent presents CTA without further probing

### Lead Classification
- Automatic post-booking classification: `hot`, `warm`, `cold`, `unqualified`
- Urgency level assessment: `immediate`, `short_term`, `long_term`
- Key indicator tracking and recommended next actions

---

## Persona & Customization

### Bot Persona Configuration
Every tenant can configure their bot with:

| Field | Description | Example |
|-------|-------------|---------|
| `name` | Bot display name | "Arya" |
| `role` | Bot's role description | "Sales Assistant" |
| `company_name` | Company name | "AI Sante" |
| `company_description` | What the company does | "AI-powered healthcare solutions" |
| `industry` | Industry vertical | "Healthcare Technology" |
| `core_features` | Product features list | ["AI Diagnostics", "Patient Portal"] |
| `core_usps` | Unique selling points | ["99.5% accuracy", "HIPAA compliant"] |
| `use_cases` | Target use cases | ["Hospital networks", "Clinics"] |
| `calendly_link` | Booking link | "https://calendly.com/..." |
| `working_hours` | Business hours config | WorkingHours model |

### Website Auto-Fill (Crawl4AI)
- **API:** `POST /autofill_persona`
- Crawls target website using BFS deep crawl strategy
- Extracts company info, features, and messaging
- Auto-populates BotPersona fields
- Simultaneously ingests crawled content into RAG knowledge base

---

## Smart Communication

### Email Transition
- Agents can detect when users prefer email
- Graceful handoff from chat to email channel
- Email validation with typo detection (e.g., "gmial.com" → "gmail.com")

### Human Escalation
- Users can request human support at any point
- Conversation context preserved for handoff
- Email collected for follow-up
- Escalation timestamp recorded

### Follow-up Scheduling
- Natural language scheduling: "remind me tomorrow", "ping me in 30 minutes"
- Timezone-aware with multi-timezone country handling
- 90-day maximum future window

### Emoji Support
- Configurable emoji usage in responses
- Contextual emoji selection based on conversation tone

---

## Safety & Guardrails

### Input Guardrail
- Runs on every user message before agent processing
- Detects: prompt injection, jailbreak attempts, harmful content
- Uses fast guardrail model (GPT-4o-mini) for low-latency classification
- **Safe Pattern Bypass:** Common greetings ("hi", "hello", "thanks") skip LLM classification entirely

### Output Guardrail
- Validates every agent response before delivery
- Checks for: off-topic content, harmful language, PII leakage
- Uses `OutputGuardrail` Pydantic model with tripwire mechanism
- Blocked responses are replaced with safe fallback messages

### Classification Categories
Input attack types: `direct_attack`, `indirect_attack`, `social_engineering`, `off_topic`, `safe`

---

## Performance & Caching

### Three-Layer Caching Strategy

| Layer | Technology | Scope | Hit Action |
|-------|-----------|-------|------------|
| **Semantic Cache** | SentenceTransformer embeddings | Per-user queries | Return cached response (skip LLM) |
| **Prompt Cache** | OpenAI prefix caching | Per-model prompt prefix | Reduced token cost + latency |
| **Session Cache** | SQLite/PostgreSQL | Per-session state | Resume conversation state |

### Cache Monitoring
- `GET /cache_stats` — View hit/miss rates, token savings
- `POST /cache_stats/reset` — Reset statistics
- Logged per-request cache decisions

---

## Analytics & Observability

### Opik Tracing
- Every agent execution, tool call, and guardrail check is traced
- `@track` decorator on key functions
- Dashboard visualization of conversation flows
- Latency and token usage tracking

### Executive Summary
- Milestone-triggered summaries (e.g., after booking, after lead classification)
- Captures: key decisions, contact details, next steps
- Stored with session data for CRM integration

### Structured Logging
- `logger`-based structured logging throughout
- Request-level context via `request_context.py` (ContextVar)
- Log levels: DEBUG, INFO, WARNING, ERROR

---

## Multi-Tenancy & Data Isolation

### Per-Tenant Isolation

| Component | Isolation Method |
|-----------|-----------------|
| Knowledge Base | Separate vector DB collection per `user_id` |
| Sessions | Separate session records per `user_id` + `session_id` |
| Cache | Per-user semantic cache entries |
| Persona | Per-tenant BotPersona configuration |

### Session Management

| Backend | Environment | Persistence |
|---------|-------------|-------------|
| SQLite | Development | Local file |
| Neon PostgreSQL | Production | Cloud persistent |

---

## Integration Capabilities

### REST API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/chat` | POST | Main chat endpoint (API clients) |
| `/chat_ui` | POST | Chat endpoint (Streamlit UI) |
| `/generate_probing_questions` | POST | Generate qualifying questions |
| `/autofill_persona` | POST | Website crawl → persona auto-fill |
| `/ingest_documents` | POST | Upload documents to RAG KB |
| `/generate_instructions` | POST | Generate probing instructions |
| `/health` | GET | Health check |
| `/cache_stats` | GET | Cache performance metrics |
| `/cache_stats/reset` | POST | Reset cache statistics |

### Streamlit Chat UI
- Full-featured web chat interface (`streamlit_ui/`)
- Authentication, thread management, persona configuration
- Knowledge base management dialog
- QA panel for testing

### Calendly API Integration
- Event type listing and matching
- Real-time availability checking
- Timezone-aware scheduling

---

*For related documentation, see:*
- [ARCHITECTURE.md](ARCHITECTURE.md) — System architecture details
- [TOOLS_REFERENCE.md](TOOLS_REFERENCE.md) — Tool specifications
- [AGENT_FLOWS.md](AGENT_FLOWS.md) — Agent interaction workflows
