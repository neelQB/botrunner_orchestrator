# BotRunner Deployment Guide

> **Last Updated:** February 6, 2026 &nbsp;|&nbsp; **Version:** 2.0.0

Deployment options, infrastructure requirements, environment configuration, monitoring, and security for the BotRunner multi-agent framework.

---

## Table of Contents

- [Deployment Options](#deployment-options)
- [Environment Configuration](#environment-configuration)
- [Infrastructure Requirements](#infrastructure-requirements)
- [Production Deployment](#production-deployment)
- [Database Setup](#database-setup)
- [Vector Database Setup](#vector-database-setup)
- [Monitoring & Observability](#monitoring--observability)
- [Security](#security)
- [Scaling](#scaling)
- [Troubleshooting](#troubleshooting)

---

## Deployment Options

### Option 1: Direct Server (Uvicorn)

Best for: Development, single-instance production

```bash
# Development
uvicorn main:emailbot --host 0.0.0.0 --port 8000 --reload

# Production
uvicorn main:emailbot --host 0.0.0.0 --port 8000 --workers 4
```

### Option 2: Docker

Best for: Containerized deployments, cloud platforms

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

```bash
docker build -t botrunner:latest .
docker run -p 8000:8000 --env-file .env botrunner:latest
```

### Option 3: Cloud Platform

Best for: Managed infrastructure, auto-scaling

| Platform | Service        | Configuration                  |
| -------- | -------------- | ------------------------------ |
| AWS      | ECS / Fargate  | Docker container, ALB frontend |
| GCP      | Cloud Run      | Auto-scaling, min 1 instance   |
| Azure    | Container Apps | Docker, managed scaling        |
| Railway  | Web Service    | Git-based deploy, auto-build   |
| Render   | Web Service    | Docker or native Python        |

---

## Environment Configuration

### Required Environment Variables

```env
# LLM API Keys (at least one required)
OPENAI_API_KEY=sk-...                    # OpenAI API key
AZURE_OPENAI_API_KEY=...                 # Azure OpenAI key (for fallback)
AZURE_OPENAI_ENDPOINT=...               # Azure endpoint URL
GEMINI_API_KEY=...                       # Google Gemini key (for fallback)

# Database
DATABASE=SQLite                           # "SQLite" or "Neon"
DATABASE_PATH=./data/botrunner.db         # SQLite path (dev)
# or
NEON_DATABASE_URL=postgresql://...        # Neon connection string (prod)

# Vector Database
VECTORDB=chromadb                         # "chromadb" or "qdrant"
CHROMA_DB_PATH=./rag/chroma_db           # ChromaDB path (dev)
# or
QDRANT_URL=https://...                   # Qdrant cloud URL (prod)
QDRANT_API_KEY=...                       # Qdrant API key
```

### Optional Environment Variables

```env
# Models (defaults shown)
PRIMARY_MODEL=gpt-4.1                    # Main conversation model
GUARDRAIL_MODEL=gpt-4o-mini             # Guardrail classification
SUMMARIZER_MODEL=gpt-4o-mini            # Conversation summarizer
FALLBACK_MODEL=gpt-4.1                  # Azure fallback model
FALLBACK_GEMINI_MODEL=gemini-3-flash    # Gemini fallback model

# Calendly
CALENDLY_API_KEY=...                     # Calendly personal access token

# Observability
OPIK_PROJECT_NAME=botrunner              # Opik project name
OPIK_API_KEY=...                         # Opik API key

# Application
ENVIRONMENT=production                   # "development" or "production"
DEBUG=false                              # Enable debug logging
MAX_HISTORY=20                           # Max conversation turns before summarization
CACHE_SIMILARITY_THRESHOLD=0.92          # Semantic cache threshold (0-1)
```

### Environment-Specific Configuration

| Setting       | Development  | Production |
| ------------- | ------------ | ---------- |
| `DATABASE`    | SQLite       | Neon       |
| `VECTORDB`    | chromadb     | qdrant     |
| `ENVIRONMENT` | development  | production |
| `DEBUG`       | true         | false      |
| Workers       | 1 (--reload) | 4+         |
| Logging       | DEBUG level  | INFO level |

---

## Infrastructure Requirements

### Minimum Requirements

| Resource    | Development    | Production     |
| ----------- | -------------- | -------------- |
| **CPU**     | 2 cores        | 4+ cores       |
| **RAM**     | 2 GB           | 4+ GB          |
| **Disk**    | 5 GB           | 20+ GB         |
| **Python**  | 3.11+          | 3.11+          |
| **Network** | Outbound HTTPS | Outbound HTTPS |

### Memory Breakdown

| Component                 | Memory Usage    |
| ------------------------- | --------------- |
| FastAPI server            | ~100 MB         |
| SentenceTransformer model | ~200 MB         |
| ChromaDB (dev)            | ~100-500 MB     |
| Per-session state         | ~2-5 MB         |
| Python runtime overhead   | ~150 MB         |
| **Total baseline**        | **~550-950 MB** |

### Network Requirements

| Service         | Protocol | Port | Purpose              |
| --------------- | -------- | ---- | -------------------- |
| OpenAI API      | HTTPS    | 443  | LLM inference        |
| Azure OpenAI    | HTTPS    | 443  | Fallback LLM         |
| Google AI       | HTTPS    | 443  | Gemini fallback      |
| Calendly API    | HTTPS    | 443  | Calendar integration |
| Qdrant Cloud    | HTTPS    | 443  | Vector DB (prod)     |
| Neon PostgreSQL | TCP      | 5432 | Database (prod)      |
| Opik            | HTTPS    | 443  | Observability        |

---

## Production Deployment

### Pre-Deployment Checklist

- [ ] All required environment variables set
- [ ] API keys validated and working
- [ ] Database connection tested
- [ ] Vector DB connection tested
- [ ] Calendly API key configured (if using booking)
- [ ] Guardrail models accessible
- [ ] Fallback models configured and accessible
- [ ] Health endpoint responds: `GET /health`
- [ ] Tests pass: `python tests/comprehensive_test.py`
- [ ] Log output verified
- [ ] CORS settings configured for production domains

### Deployment Steps

```bash
# 1. Set environment variables
export $(cat .env.production | xargs)

# 2. Install production dependencies
pip install -r requirements.txt

# 3. Validate configuration
python -c "from emailbot.config.settings import settings; print(settings.is_production)"

# 4. Run health check
python -c "
import asyncio
from main import app
print('App loaded successfully')
"

# 5. Start production server
uvicorn main:emailbot \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 4 \
  --log-level info \
  --access-log
```

### Health Check

```bash
curl http://localhost:8000/health
# Expected: {"status": "healthy"}
```

### Reverse Proxy (Nginx)

```nginx
upstream botrunner {
    server 127.0.0.1:8000;
}

server {
    listen 443 ssl;
    server_name api.yourdomain.com;

    ssl_certificate /etc/ssl/certs/cert.pem;
    ssl_certificate_key /etc/ssl/private/key.pem;

    location / {
        proxy_pass http://botrunner;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket support (if needed)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        # Timeouts (LLM calls can take time)
        proxy_read_timeout 60s;
        proxy_send_timeout 60s;
    }
}
```

---

## Database Setup

### SQLite (Development)

```env
DATABASE=SQLite
DATABASE_PATH=./data/botrunner.db
```

- Auto-created on first startup
- No additional setup needed
- File-based, single-writer

### Neon PostgreSQL (Production)

```env
DATABASE=Neon
NEON_DATABASE_URL=postgresql://user:pass@ep-xxx.us-east-2.aws.neon.tech/botrunner?sslmode=require
```

**Setup steps:**

1. Create a Neon project at [neon.tech](https://neon.tech)
2. Create a database named `botrunner`
3. Copy the connection string
4. Tables are auto-created via `SessionManagerBase.initialize()`

**Schema (auto-created):**

```sql
CREATE TABLE IF NOT EXISTS sessions (
    user_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    state_data JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (user_id, session_id)
);
```

---

## Vector Database Setup

### ChromaDB (Development)

```env
VECTORDB=chromadb
CHROMA_DB_PATH=./rag/chroma_db
```

- Persistent local storage
- Auto-creates collections on document ingestion
- No additional setup needed

### Qdrant (Production)

```env
VECTORDB=qdrant
QDRANT_URL=https://xxx.us-east-1.aws.cloud.qdrant.io
QDRANT_API_KEY=...
```

**Setup steps:**

1. Create a Qdrant Cloud cluster at [qdrant.tech](https://qdrant.tech)
2. Note the cluster URL and API key
3. Collections are auto-created on document ingestion
4. Embedding dimension: 384 (all-MiniLM-L6-v2)

---

## Monitoring & Observability

### Built-in Monitoring

| Endpoint             | Method | Purpose                       |
| -------------------- | ------ | ----------------------------- |
| `/health`            | GET    | Service health check          |
| `/cache_stats`       | GET    | Prompt cache hit/miss metrics |
| `/cache_stats/reset` | POST   | Reset cache statistics        |

### Opik Tracing

Configure Opik for full execution tracing:

```env
OPIK_PROJECT_NAME=botrunner-production
OPIK_API_KEY=your-opik-key
```

**What's traced:**

- Every agent execution
- Every tool call with parameters and results
- Guardrail evaluations
- Handoff events
- LLM token usage

### Logging

BotRunner uses `logger` for structured logging:

```python
# Logs include:
# - Timestamp
# - Level (DEBUG/INFO/WARNING/ERROR)
# - Module name
# - User ID and session ID (via request_context)
# - Message with structured data
```

**Production log configuration:**

- Set `DEBUG=false` for INFO-level logging
- Redirect logs to file or log aggregator
- Use structured JSON format for log analysis

### Recommended Monitoring Stack

| Component | Tool                  | Purpose                    |
| --------- | --------------------- | -------------------------- |
| APM       | Opik                  | Agent execution tracing    |
| Logs      | ELK / Datadog         | Log aggregation and search |
| Metrics   | Prometheus + Grafana  | Custom metrics dashboard   |
| Uptime    | UptimeRobot / Pingdom | Health endpoint monitoring |
| Alerts    | PagerDuty / Slack     | Error rate, latency alerts |

### Key Alerts to Configure

| Alert                          | Condition                          | Severity |
| ------------------------------ | ---------------------------------- | -------- |
| High error rate                | > 5% of requests return 500        | Critical |
| High latency                   | P95 > 10s                          | Warning  |
| Fallback model active          | Primary model consistently failing | Warning  |
| Database connection failure    | Connection pool exhausted          | Critical |
| Guardrail false positive spike | > 10% block rate in 1 hour         | Warning  |
| Memory usage                   | > 80% of allocation                | Warning  |

---

## Security

### API Key Management

| Key                  | Storage                                | Rotation  |
| -------------------- | -------------------------------------- | --------- |
| OPENAI_API_KEY       | Environment variable / Secrets manager | Monthly   |
| AZURE_OPENAI_API_KEY | Environment variable / Secrets manager | Monthly   |
| GEMINI_API_KEY       | Environment variable / Secrets manager | Monthly   |
| CALENDLY_API_KEY     | Environment variable / Secrets manager | Quarterly |
| QDRANT_API_KEY       | Environment variable / Secrets manager | Quarterly |
| NEON_DATABASE_URL    | Environment variable / Secrets manager | Quarterly |

**Best practices:**

- Never commit API keys to source control
- Use secrets managers (AWS Secrets Manager, HashiCorp Vault, etc.)
- Rotate keys regularly
- Use separate keys for development and production

### Data Security

| Data                 | Protection                                         |
| -------------------- | -------------------------------------------------- |
| Conversation data    | Per-tenant isolation, encrypted at rest (DB level) |
| Knowledge base       | Tenant-isolated collections                        |
| API keys             | Environment variables, not in code                 |
| PII in conversations | Output guardrail prevents leakage                  |

### Network Security

- All external API calls use HTTPS
- Database connections use SSL (`sslmode=require`)
- Reverse proxy with TLS termination recommended
- CORS configuration for allowed origins

### Input Protection

- Input guardrail blocks prompt injection attempts
- Attack classification: `direct_attack`, `indirect_attack`, `social_engineering`, `off_topic`
- Safe conversational pattern bypass prevents over-blocking

---

## Scaling

### Horizontal Scaling

```bash
# Multiple workers (CPU-bound scaling)
uvicorn main:emailbot --workers 8

# Behind load balancer (multiple instances)
# Each instance is stateless — session state in DB
```

### Scaling Considerations

| Component       | Scaling Strategy                         |
| --------------- | ---------------------------------------- |
| FastAPI server  | Add workers or instances behind LB       |
| Session state   | Already in external DB (Neon)            |
| Vector DB       | Qdrant Cloud auto-scales                 |
| Semantic cache  | In-memory per-instance (no shared cache) |
| Embedding model | Loaded per-instance (~200MB)             |
| LLM calls       | Rate-limited by API provider             |

### Bottlenecks

| Bottleneck               | Solution                               |
| ------------------------ | -------------------------------------- |
| LLM latency              | Prompt caching, semantic caching       |
| Embedding model load     | Singleton pattern, pre-warm on startup |
| Database connections     | Connection pooling (asyncpg for Neon)  |
| Memory (embedding model) | 200MB per instance — ensure allocation |
| Concurrent LLM calls     | LiteLLM Router handles queuing         |

---

## Troubleshooting

### Common Production Issues

| Issue                   | Diagnosis                             | Resolution                                  |
| ----------------------- | ------------------------------------- | ------------------------------------------- |
| 500 errors on `/chat`   | Check logs for stack trace            | Usually API key or model config issue       |
| Slow responses          | Check `/cache_stats` for low hit rate | Tune CACHE_SIMILARITY_THRESHOLD             |
| Missing KB results      | Verify collection exists              | Re-ingest documents via `/ingest_documents` |
| Session not persisting  | Check DB connection                   | Verify NEON_DATABASE_URL or DATABASE_PATH   |
| Guardrail over-blocking | Check guardrail model                 | Tune guardrail prompt or add safe patterns  |
| Fallback model active   | Primary model down or rate-limited    | Check OpenAI status, verify API key         |
| Memory growth           | Semantic cache unbounded              | Implement cache eviction or restart         |
| Startup failure         | Missing env vars                      | Check all required env vars are set         |

### Diagnostic Commands

```bash
# Check if server is running
curl http://localhost:8000/health

# Check cache performance
curl http://localhost:8000/cache_stats

# Check logs
tail -f /var/log/botrunner/emailbot.log

# Test a conversation
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test", "session_id": "diag", "user_query": "Hello"}'
```

---

_For related documentation, see:_

- [ARCHITECTURE.md](ARCHITECTURE.md) — System architecture
- [DEVELOPERS.md](DEVELOPERS.md) — Development setup
- [QA.md](QA.md) — Testing and quality assurance
