# BotRunner Product Management Guide

> **Last Updated:** February 6, 2026 &nbsp;|&nbsp; **Version:** 2.0.0

Product vision, user stories, competitive positioning, and roadmap for the BotRunner multi-agent framework.

---

## Table of Contents

- [Product Vision](#product-vision)
- [Target Users](#target-users)
- [User Stories](#user-stories)
- [Feature Prioritization](#feature-prioritization)
- [Competitive Positioning](#competitive-positioning)
- [Metrics & KPIs](#metrics--kpis)
- [Roadmap](#roadmap)

---

## Product Vision

### Mission Statement
BotRunner provides an **intelligent, multi-agent AI sales assistant** that automates lead qualification, demo booking, and customer engagement — enabling sales teams to focus on closing deals instead of repetitive conversations.

### Value Proposition
- **For sales teams** who need to qualify leads 24/7 without additional headcount
- **BotRunner** is a multi-agent AI framework
- **That** handles complete sales conversations from first contact to demo booking
- **Unlike** static chatbots or simple FAQ bots
- **Our product** uses intelligent agent orchestration with context-aware handoffs, probing-based lead qualification, and seamless calendar integration

### Core Differentiators
1. **Multi-agent orchestration** — Not a single monolithic bot, but 7 specialized agents collaborating
2. **Dynamic persona** — Fully configurable per tenant, auto-fillable from website crawling
3. **Intelligent probing** — Score-based lead qualification woven into natural conversation
4. **Production-grade resilience** — 3-tier model fallback, guardrails, semantic caching
5. **Multi-tenant by design** — Complete data isolation per customer

---

## Target Users

### Primary Personas

| Persona | Role | Need |
|---------|------|------|
| **Sales Leader** | VP Sales, Sales Manager | Automate top-of-funnel, qualify more leads, book more demos |
| **Product Owner** | Configures the bot | Easy persona setup, probing question design, KB management |
| **Developer** | Integrates/extends | Clean APIs, clear architecture, extensibility |
| **End User (Prospect)** | Visits website/chats | Natural conversation, quick answers, easy booking |

### Tenant Profile
- B2B SaaS companies with sales-led growth
- Companies with high-volume inbound inquiries
- Teams looking to automate lead qualification
- Organizations needing 24/7 first-response capability

---

## User Stories

### Epic 1: Lead Qualification

| ID | Story | Priority | Status |
|----|-------|----------|--------|
| US-101 | As a **prospect**, I want to ask about products and get accurate answers from the company's knowledge base | P0 | ✅ Done |
| US-102 | As a **sales leader**, I want the bot to ask qualifying questions naturally during conversation | P0 | ✅ Done |
| US-103 | As a **product owner**, I want to define custom probing questions with score weights | P0 | ✅ Done |
| US-104 | As a **sales leader**, I want leads automatically classified (hot/warm/cold) after interactions | P0 | ✅ Done |
| US-105 | As a **product owner**, I want the bot to stop probing after the prospect objects 3 times | P1 | ✅ Done |
| US-106 | As a **product owner**, I want a CTA triggered automatically when qualification score is reached | P1 | ✅ Done |

### Epic 2: Demo Booking

| ID | Story | Priority | Status |
|----|-------|----------|--------|
| US-201 | As a **prospect**, I want to book a demo by saying a natural date/time | P0 | ✅ Done |
| US-202 | As a **prospect**, I want my timezone handled automatically | P0 | ✅ Done |
| US-203 | As a **prospect**, I want to reschedule my demo easily | P1 | ✅ Done |
| US-204 | As a **prospect**, I want to cancel my demo | P1 | ✅ Done |
| US-205 | As a **product owner**, I want working hours and holidays configured | P1 | ✅ Done |
| US-206 | As a **sales leader**, I want Calendly availability checked in real time | P0 | ✅ Done |

### Epic 3: Conversation Experience

| ID | Story | Priority | Status |
|----|-------|----------|--------|
| US-301 | As a **prospect**, I want a natural, friendly conversation (not robotic) | P0 | ✅ Done |
| US-302 | As a **prospect**, I want to be handed to a human when I ask | P0 | ✅ Done |
| US-303 | As a **prospect**, I want to switch to email communication if I prefer | P1 | ✅ Done |
| US-304 | As a **prospect**, I want to schedule a follow-up at a time that works for me | P1 | ✅ Done |
| US-305 | As a **product owner**, I want the bot persona (name, tone, company info) fully customizable | P0 | ✅ Done |
| US-306 | As a **product owner**, I want persona auto-filled from our website | P2 | ✅ Done |

### Epic 4: Safety & Trust

| ID | Story | Priority | Status |
|----|-------|----------|--------|
| US-401 | As an **operator**, I want prompt injection and jailbreak attempts blocked | P0 | ✅ Done |
| US-402 | As an **operator**, I want off-topic or harmful responses caught before delivery | P0 | ✅ Done |
| US-403 | As a **prospect**, I want my conversation data isolated from other tenants | P0 | ✅ Done |
| US-404 | As an **operator**, I want the bot to gracefully handle service failures | P0 | ✅ Done |

### Epic 5: Developer Experience

| ID | Story | Priority | Status |
|----|-------|----------|--------|
| US-501 | As a **developer**, I want a clean REST API to integrate with any frontend | P0 | ✅ Done |
| US-502 | As a **developer**, I want to add new agents without modifying existing code | P1 | ✅ Done |
| US-503 | As a **developer**, I want full observability (tracing, logging, metrics) | P1 | ✅ Done |
| US-504 | As a **developer**, I want comprehensive documentation | P1 | ✅ Done |

---

## Feature Prioritization

### MoSCoW Analysis (Current State)

| Priority | Features |
|----------|----------|
| **Must Have** | Multi-agent routing, RAG search, demo booking, input guardrail, session management, API endpoints |
| **Should Have** | Lead classification, probing system, output guardrail, semantic caching, conversation summarization |
| **Could Have** | Website crawl auto-fill, prompt caching optimization, executive summaries, emoji configuration |
| **Won't Have (Now)** | Real-time voice, multi-language, CRM push integration, A/B testing framework |

### Feature Maturity

| Feature | Maturity Level |
|---------|---------------|
| Agent orchestration | Production-ready |
| RAG retrieval | Production-ready |
| Demo booking | Production-ready |
| Guardrails | Production-ready |
| Probing engine | Production-ready |
| Calendly integration | Production-ready |
| Semantic caching | Production-ready |
| Website crawler | Production-ready |
| Prompt caching | Production-ready |
| Streamlit UI | Beta |

---

## Competitive Positioning

### Comparison Matrix

| Capability | BotRunner | Generic Chatbot | Single-Agent Bot | Rule-Based Bot |
|-----------|-----------|----------------|-----------------|----------------|
| Multi-agent orchestration | ✅ | ❌ | ❌ | ❌ |
| Dynamic persona config | ✅ | Partial | Partial | ❌ |
| RAG knowledge base | ✅ | Partial | ✅ | ❌ |
| Lead qualification | ✅ | ❌ | Partial | Rule-based |
| Calendar integration | ✅ | ❌ | Partial | Partial |
| Guardrails (in + out) | ✅ | Partial | Partial | N/A |
| Multi-model fallback | ✅ | ❌ | ❌ | N/A |
| Multi-tenant isolation | ✅ | Partial | ❌ | Partial |
| Website auto-fill | ✅ | ❌ | ❌ | ❌ |
| Semantic caching | ✅ | ❌ | ❌ | ❌ |
| Human escalation | ✅ | Basic | Basic | Basic |

### Key Advantages
1. **Architecture:** Multi-agent design enables each agent to be independently optimized
2. **Safety:** Dual guardrails (input + output) with fast-path bypass for performance
3. **Resilience:** 3-tier model fallback ensures 99%+ uptime
4. **Cost Efficiency:** Prompt caching + semantic caching reduce LLM costs
5. **Extensibility:** Factory pattern makes adding agents/tools straightforward

---

## Metrics & KPIs

### Business Metrics

| Metric | Description | Target |
|--------|-------------|--------|
| **Demo Booking Rate** | % of conversations that result in a booked demo | > 15% |
| **Lead Qualification Rate** | % of leads successfully classified | > 80% |
| **Hot Lead Rate** | % of qualified leads classified as "hot" | > 20% |
| **Escalation Rate** | % of conversations requiring human handoff | < 15% |
| **Response Satisfaction** | User satisfaction with bot responses | > 4.0/5.0 |

### Technical Metrics

| Metric | Description | Target |
|--------|-------------|--------|
| **Response Latency (P50)** | Median response time | < 2s |
| **Response Latency (P95)** | 95th percentile response time | < 5s |
| **Cache Hit Rate** | % of queries served from semantic cache | > 20% |
| **Prompt Cache Hit Rate** | % of prompt prefixes cached by OpenAI | > 60% |
| **Guardrail False Positive Rate** | % of safe messages incorrectly blocked | < 2% |
| **Uptime** | Service availability | > 99.5% |
| **Error Rate** | % of requests returning errors | < 1% |

### Operational Metrics

| Metric | Description | Monitoring |
|--------|-------------|------------|
| Active sessions | Concurrent user sessions | Real-time |
| Token usage | LLM token consumption per conversation | Per-request |
| Fallback activation | % of requests hitting fallback models | Per-hour |
| KB coverage | % of queries answered from knowledge base | Daily |

---

## Roadmap

### Current Release (v2.0.0)
✅ All features listed in [PRODUCT_FEATURES.md](PRODUCT_FEATURES.md) are implemented and production-ready.

### Near-Term Enhancements

| Feature | Description | Priority |
|---------|-------------|----------|
| CRM Integration | Push lead data to Salesforce/HubSpot | P1 |
| Analytics Dashboard | Visual metrics for conversation quality and lead funnel | P1 |
| A/B Testing | Compare agent prompt variations | P2 |
| Webhook Notifications | Real-time alerts for hot leads, bookings, escalations | P1 |
| Multi-Language(Currently Beta) | Support for non-English conversations | P2 |

### Medium-Term Vision

| Feature | Description | Priority |
|---------|-------------|----------|
| Voice Integration | Speech-to-text / text-to-speech support | P2 |
| Email Sequences | Automated follow-up email campaigns | P2 |
| Custom Agent Builder | No-code agent creation interface | P3 |
| Conversation Analytics | NLP-based conversation quality analysis | P2 |

### Long-Term Vision

| Feature | Description |
|---------|-------------|
| Predictive Lead Scoring | ML-based lead quality prediction |
| Autonomous Deal Progression | Multi-touch automated sales sequences |
| Industry Templates | Pre-built personas and KB for verticals |
| Self-Improving Agents | Feedback loop for continuous prompt optimization |

---

*For related documentation, see:*
- [PRODUCT_FEATURES.md](PRODUCT_FEATURES.md) — Complete feature catalog
- [ARCHITECTURE.md](ARCHITECTURE.md) — Technical architecture
- [QA.md](QA.md) — Quality assurance and testing
