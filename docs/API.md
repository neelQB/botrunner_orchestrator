# BotRunner API Documentation

## Overview

BotRunner exposes a REST API built with FastAPI for chatbot interactions. All endpoints support JSON request/response formats.

## Base URL

```
Development: http://localhost:8000
Production:  https://your-domain.com/api
```

## Authentication

All API endpoints require Bearer token authentication:

```http
Authorization: Bearer <your-api-token>
```

The token is validated against the `API_AUTH_TOKEN` environment variable.

---

## Endpoints

### Health Check

#### GET `/health`

Check API server health status.

**Authentication:** None required

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

---

### Chat

#### POST `/chat`

Main chat endpoint for conversational interactions.

**Authentication:** Required

**Request Body:**
```json
{
  "user_id": "string",
  "user_query": "string",
  "tenant_id": "string (optional)",
  "chat_history": [
    {"role": "user", "content": "Hello"},
    {"role": "assistant", "content": "Hi there!"}
  ],
  "persona": {
    "name": "string (optional)",
    "company_name": "string (optional)",
    "company_description": "string (optional)"
  }
}
```

**Request Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `user_id` | string | Yes | Unique identifier for the user |
| `user_query` | string | Yes | User's message/query |
| `tenant_id` | string | No | Tenant identifier for multi-tenant setup |
| `chat_history` | array | No | Previous conversation messages |
| `persona` | object | No | Custom bot persona configuration |

**Response:**
```json
{
  "response": "string",
  "user_id": "string",
  "session_id": "string",
  "agent_name": "string",
  "collected_fields": {
    "name": "John",
    "email": "john@example.com"
  },
  "probing_details": {
    "questions": [...],
    "progress_percentage": 60
  },
  "guardrail_decision": {
    "is_attack_query": false,
    "reason": null
  }
}
```

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `response` | string | Bot's response message |
| `user_id` | string | User identifier |
| `session_id` | string | Session identifier |
| `agent_name` | string | Name of agent that handled request |
| `collected_fields` | object | Information collected from user |
| `probing_details` | object | Probing question context |
| `guardrail_decision` | object | Input guardrail evaluation result |

**Example:**
```bash
curl -X POST "http://localhost:8000/chat" \
  -H "Authorization: Bearer your-token" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user_123",
    "user_query": "I want to book a demo"
  }'
```

---

### Chat UI

#### POST `/chat_ui`

Chat endpoint optimized for UI integrations (e.g., Streamlit).

**Authentication:** Required

**Request Body:**
```json
{
  "user_id": "string",
  "user_query": "string",
  "tenant_id": "string (optional)",
  "chat_history": [],
  "chat_summary": "string (optional)",
  "executive_summary": "string (optional)",
  "contact_details": {
    "name": "string",
    "email": "string",
    "phone": "string",
    "company_name": "string"
  },
  "collected_fields": {},
  "persona": {}
}
```

**Additional Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `chat_summary` | string | Summarized conversation context |
| `executive_summary` | string | High-level conversation summary |
| `contact_details` | object | Pre-collected contact information |
| `collected_fields` | object | Previously collected form fields |

**Response:**
```json
{
  "response": "string",
  "user_id": "string",
  "session_id": "string",
  "chat_history": [...],
  "chat_summary": "string",
  "executive_summary": "string",
  "collected_fields": {},
  "contact_details": {},
  "probing_details": {},
  "all_info_collected": false,
  "booking_confirmed": false
}
```

---

### Generate Probing Questions

#### POST `/generate_probing_questions`

Generate intelligent probing questions based on conversation context.

**Authentication:** Required

**Request Body:**
```json
{
  "user_id": "string",
  "conversation_context": "string",
  "collected_fields": {
    "name": "John"
  },
  "persona": {
    "company_name": "AI Sante",
    "company_products": [...]
  }
}
```

**Response:**
```json
{
  "questions": [
    {
      "question": "What is your current budget for this solution?",
      "priority": "high",
      "category": "budget"
    },
    {
      "question": "How many team members would use this?",
      "priority": "medium",
      "category": "team_size"
    }
  ],
  "progress_percentage": 45,
  "missing_fields": ["budget", "timeline", "team_size"]
}
```

---

## Data Models

### BotState

Complete state container for a conversation session.

```json
{
  "user_context": {
    "user_id": "string",
    "user_query": "string",
    "tenant_id": "string",
    "chat_history": [],
    "chat_summary": "string",
    "executive_summary": "string",
    "retrieved_docs": [],
    "contact_details": {},
    "collected_fields": {},
    "all_info_collected": false,
    "booking_confirmed": false,
    "timezone": "string",
    "region_code": "string"
  },
  "bot_persona": {
    "name": "string",
    "company_name": "string",
    "company_domain": "string",
    "company_description": "string",
    "company_products": [],
    "core_usps": "string",
    "core_features": "string",
    "contact_info": "string",
    "language": "en",
    "rules": [],
    "personality": "string",
    "use_emoji": true
  },
  "response": "string",
  "session_id": "string",
  "conversation_id": "string",
  "input_guardrail_decision": {},
  "output_guardrail_decision": {},
  "probing_context": {},
  "probing_details": {}
}
```

### ContactDetails

```json
{
  "name": "string",
  "email": "string",
  "phone": "string",
  "company_name": "string",
  "job_title": "string",
  "country": "string"
}
```

### Products

```json
{
  "id": "string",
  "name": "string",
  "description": "string"
}
```

### ProbingQuestion

```json
{
  "question": "string",
  "priority": "high|medium|low",
  "category": "string",
  "asked": false,
  "answer": null
}
```

---

## Error Responses

### 400 Bad Request

Invalid request parameters or body.

```json
{
  "detail": "Invalid request body",
  "errors": [
    {
      "loc": ["body", "user_id"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

### 401 Unauthorized

Missing or invalid authentication token.

```json
{
  "detail": "Invalid or missing authentication token"
}
```

### 500 Internal Server Error

Server-side error during processing.

```json
{
  "detail": "Internal server error",
  "error_type": "AgentExecutionError",
  "message": "Agent execution failed"
}
```

---

## Rate Limiting

Default rate limits (configurable via environment):

| Endpoint | Limit |
|----------|-------|
| `/chat` | 100 requests/minute per user |
| `/chat_ui` | 100 requests/minute per user |
| `/generate_probing_questions` | 50 requests/minute per user |

---

## Webhooks (Future)

Planned webhook support for:

- Conversation completion notifications
- Booking confirmation events
- Human escalation triggers
- Lead qualification updates

---

## SDKs & Client Libraries

### Python

```python
import requests

class BotRunnerClient:
    def __init__(self, base_url: str, api_token: str):
        self.base_url = base_url
        self.headers = {"Authorization": f"Bearer {api_token}"}
    
    def chat(self, user_id: str, query: str, **kwargs):
        response = requests.post(
            f"{self.base_url}/chat",
            headers=self.headers,
            json={"user_id": user_id, "user_query": query, **kwargs}
        )
        response.raise_for_status()
        return response.json()

# Usage
client = BotRunnerClient("http://localhost:8000", "your-token")
result = client.chat("user_123", "Tell me about your products")
print(result["response"])
```

### JavaScript/TypeScript

```typescript
interface ChatRequest {
  user_id: string;
  user_query: string;
  tenant_id?: string;
  chat_history?: Array<{role: string; content: string}>;
}

interface ChatResponse {
  response: string;
  user_id: string;
  session_id: string;
  agent_name: string;
  collected_fields: Record<string, any>;
}

class BotRunnerClient {
  constructor(
    private baseUrl: string,
    private apiToken: string
  ) {}

  async chat(request: ChatRequest): Promise<ChatResponse> {
    const response = await fetch(`${this.baseUrl}/chat`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${this.apiToken}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    });
    
    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }
    
    return response.json();
  }
}

// Usage
const client = new BotRunnerClient('http://localhost:8000', 'your-token');
const result = await client.chat({
  user_id: 'user_123',
  user_query: 'I need help with pricing'
});
console.log(result.response);
```

---

## Environment Variables

Required environment variables for API operation:

```env
# Authentication
API_AUTH_TOKEN=your-secure-token

# OpenAI
OPENAI_API_KEY=sk-...

# Database
DATABASE_URL=sqlite:///./botrunner.db
# or
NEON_DB_URL=postgresql://...

# Optional
MAX_HISTORY=15
LOG_LEVEL=INFO
CHATBOT_NAME=Arya
```

---

## Testing

### Using cURL

```bash
# Health check
curl http://localhost:8000/health

# Chat request
curl -X POST http://localhost:8000/chat \
  -H "Authorization: Bearer test-token" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test", "user_query": "Hello"}'
```

### Using HTTPie

```bash
# Chat request
http POST localhost:8000/chat \
  Authorization:"Bearer test-token" \
  user_id=test \
  user_query="Tell me about your services"
```

### Using Python requests

```python
import requests

response = requests.post(
    "http://localhost:8000/chat",
    headers={"Authorization": "Bearer test-token"},
    json={"user_id": "test", "user_query": "Hello"}
)
print(response.json())
```
