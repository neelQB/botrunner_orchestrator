# BotRunner Agent Interaction Flows

> **Last Updated:** February 6, 2026 &nbsp;|&nbsp; **Version:** 2.0.0

This document describes the detailed interaction flows for each agent in the BotRunner system, including sample conversations, processing steps, multi-agent collaboration patterns, and error handling.

---

## Table of Contents

- [Main (Triage) Agent Flows](#main-triage-agent-flows)
- [Sales Agent Flows](#sales-agent-flows)
- [Demo Booking Agent Flows](#demo-booking-agent-flows)
- [Follow-up Agent Flows](#follow-up-agent-flows)
- [Human Escalation Agent Flows](#human-escalation-agent-flows)
- [Proceed Email Agent Flows](#proceed-email-agent-flows)
- [Lead Analysis Agent Flows](#lead-analysis-agent-flows)
- [Cross-Agent Workflows](#cross-agent-workflows)
- [Probing System Flows](#probing-system-flows)
- [Standalone Agent Flows](#standalone-agent-flows)

---

## Main (Triage) Agent Flows

**Agent:** `main_agent` &nbsp;|&nbsp; **File:** `app/agents/definitions.py` → `dynamic_main_instructions()`

### Purpose
The root agent that receives all user messages first. It classifies user intent and either responds directly or hands off to a specialized agent.

### Capabilities
- Intent classification and routing
- Greeting and small talk handling
- Trigger email communication flow (via `proceed_with_email` tool)
- Handoff to: Sales, Demo Booking, Follow-up, Human

### Flow 1: Direct Response (Greeting)

**Trigger:** User sends a greeting or simple question

```
User: "Hi there!"

Processing:
1. Input guardrail: "Hi there!" matches SAFE_CONVERSATIONAL_PATTERNS → PASS (no LLM call)
2. Main agent processes greeting
3. Generates personalized greeting using bot persona
4. Output guardrail validates response

Bot: "Hello! 👋 I'm Arya from AI Sante. How can I help you today?"
```

### Flow 2: Handoff to Sales

**Trigger:** User asks about products, pricing, features, or company

```
User: "What products do you offer?"

Processing:
1. Input guardrail: LLM classification → safe
2. Main agent classifies intent → product inquiry
3. Handoff to sales_agent triggered
4. on_sales_handoff callback: sets new_booking=True
5. Sales agent takes over
6. Sales agent calls retrieve_query tool → RAG search
7. Sales agent generates response with product info

Bot: "We offer two main products: AI Sales Bot for automated sales conversations 
      and Support Copilot for AI-powered customer support. Would you like to hear 
      more about either one?"
```

### Flow 3: Handoff to Demo Booking

**Trigger:** User wants to schedule a demo

```
User: "I'd like to book a demo"

Processing:
1. Input guardrail → safe
2. Main agent classifies intent → booking request
3. Handoff to demo_booking_agent
4. on_demo_handoff callback: sets new_booking=True
5. Demo booking agent begins collection flow

Bot: "I'd love to set up a demo for you! Could you share your email address 
      so I can send you the confirmation?"
```

### Flow 4: Handoff to Human

**Trigger:** User explicitly requests human support

```
User: "I want to talk to a real person"

Processing:
1. Input guardrail → safe
2. Main agent classifies intent → human escalation
3. Handoff to human_agent
4. on_human_handoff callback:
   - sets human_requested=True
   - records escalation_timestamp
5. Human agent provides handoff experience

Bot: "I understand you'd like to speak with someone from our team. 
      Could you share your email so we can have a team member reach out to you?"
```

### Error Handling
- **Input guardrail triggered:** Returns "I'm unable to process that request" response
- **Agent execution timeout:** Fallback to generic response
- **LLM failure:** Multi-model fallback (GPT-4.1 → Azure → Gemini)

---

## Sales Agent Flows

**Agent:** `sales_agent` &nbsp;|&nbsp; **Tools:** `retrieve_query`

### Purpose
Handle product inquiries, company information requests, pricing questions, and feature comparisons using the RAG knowledge base.

### Flow 1: Product Information Query

**Trigger:** User asks about specific product features

```
User: "What are the key features of the AI Sales Bot?"

Processing:
1. Sales agent receives query
2. Calls retrieve_query("What are the key features of the AI Sales Bot?")
   → ChromaDB/Qdrant search with tenant-isolated collection
   → Returns top-10 relevant documents
3. Agent synthesizes retrieved documents with persona context
4. Generates comprehensive response

Bot: "The AI Sales Bot includes several powerful features:
      • Multi-agent orchestration for complex conversations
      • RAG integration for knowledge-based responses
      • Lead qualification with intelligent probing
      • Calendly integration for demo booking
      Would you like to see it in action with a demo?"
```

### Flow 2: Knowledge Base Miss

**Trigger:** Query about topic not in knowledge base

```
User: "Do you offer custom integrations?"

Processing:
1. Sales agent calls retrieve_query()
   → No relevant documents found (below similarity threshold)
   → Returns: "No relevant documents found in the knowledge base..."
2. Agent falls back to persona-based knowledge
3. Uses company_description, core_features, core_usps from BotPersona

Bot: "While I don't have specific details about custom integrations, 
      I'd recommend connecting with our team to discuss your specific needs. 
      Would you like to book a call with our solutions team?"
```

### Flow 3: Probing During Sales (when enabled)

```
User: "Tell me about your pricing"

Processing:
1. Sales agent retrieves pricing info from KB
2. If enable_probing=True and probing questions configured:
   - Agent weaves probing question into response
   - ProbingEngine tracks score
3. Response includes both info and qualifying question

Bot: "Our pricing is tailored to your needs. Before I share details, 
      could you tell me about the size of your sales team? This will help me 
      recommend the right plan."
```

---

## Demo Booking Agent Flows

**Agent:** `demo_booking_agent` &nbsp;|&nbsp; **Tools:** `get_timezone`, `process_booking_datetime`, `check_calendly_availability`, `lead_analysis_tool`

### Purpose
Manage the complete demo booking lifecycle: new bookings, rescheduling, and cancellations.

### Flow 1: New Booking (Complete Flow)

```
User: "I'd like to book a demo"
Bot:  "I'd love to set up a demo! Could you share your email address?"

User: "john@gamil.com"
Processing:
  - Note: This is handled by the demo agent collecting fields
  - Email stored in collected_fields

Bot:  "Thanks, John! When would you like to schedule the demo? 
       (e.g., 'tomorrow at 3 PM', 'next Monday')"

User: "Tomorrow at 3 PM"
Processing:
  1. get_timezone(region_code) → "America/New_York"
  2. process_booking_datetime("tomorrow at 3 PM", "America/New_York")
     → Parses: date=2026-02-07, time=15:00
     → Validates: within working hours (Mon-Fri 10:00-19:00) ✓
     → Validates: not in past ✓
     → Converts to UTC: 2026-02-07T20:00:00Z
  3. check_calendly_availability(tenant_id, slot_datetime)
     → Returns: available=True, slots=[...]
  4. Booking confirmed → booking_confirmed=True
  5. lead_analysis_tool called
     → Lead classified as "warm" based on engagement

Bot:  "Your demo is confirmed for tomorrow, February 7th at 3:00 PM EST! 
       A confirmation will be sent to john@gmail.com. Looking forward to it! 🎉"
```

### Flow 2: Rescheduling

```
User: "I need to reschedule my demo"
Processing:
  - booking_type set to "reschedule"
  - Previous date/time loaded from state

Bot:  "No problem! Your current demo is scheduled for Feb 7 at 3 PM. 
       When would you like to reschedule to?"

User: "Next Wednesday at 2 PM"
Processing:
  1. process_booking_datetime("next Wednesday at 2 PM", timezone)
  2. Validation + UTC conversion
  3. check_calendly_availability
  4. Booking updated

Bot:  "Done! Your demo has been rescheduled to Wednesday, February 11th at 2:00 PM."
```

### Flow 3: Cancellation

```
User: "I need to cancel my demo"
Processing:
  - booking_type set to "cancel"
  - booking_confirmed reset

Bot:  "I'm sorry to hear that. Your demo has been cancelled. 
       Is there anything else I can help with, or would you like to reschedule later?"
```

### Flow 4: DateTime Validation Failure

```
User: "Book me a demo for last Monday"
Processing:
  1. process_booking_datetime("last Monday", timezone)
  2. Validation → date is in the past
  3. Returns: is_past=True, next_action="ask_correction"

Bot:  "It looks like that date has already passed. Could you suggest a future date? 
       I have availability this week on Wednesday and Thursday."
```

### Flow 5: Outside Working Hours

```
User: "How about Saturday at 10 AM?"
Processing:
  1. process_booking_datetime("Saturday at 10 AM", timezone)
  2. Validation → Saturday is a holiday per WorkingHours config
  3. Returns error with working hours info

Bot:  "Our demo slots are available Monday through Friday, 10 AM to 7 PM. 
       Would next Monday work for you?"
```

---

## Follow-up Agent Flows

**Agent:** `followup_agent` &nbsp;|&nbsp; **Tools:** `get_timezone`, `process_followup_datetime`

### Purpose
Schedule future interactions when users want to be contacted later.

### Flow 1: Relative Time Follow-up

```
User: "Ping me in 30 minutes"
Processing:
  1. on_followup_handoff: follow_trigger=True
  2. process_followup_datetime("in 30 minutes", "Asia/Kolkata")
     → now + 30 minutes
     → Validation: not past ✓, not >90 days future ✓
  3. followup_details updated:
     - followup_flag=True
     - followup_time="2026-02-06T15:00:00+05:30"

Bot:  "Got it! I'll follow up with you in 30 minutes at 3:00 PM IST. Talk soon! 😊"
```

### Flow 2: Named Day Follow-up

```
User: "Contact me next Monday morning"
Processing:
  1. process_followup_datetime("next Monday morning", "America/New_York")
     → Resolves: next Monday, 10:00 AM (morning default)
     → UTC conversion
  2. followup_details set

Bot:  "I'll reach out next Monday, February 9th at 10:00 AM EST. Have a great weekend!"
```

### Flow 3: Multiple Timezone Handling

```
User: [region_code suggests "US" which has multiple timezones]
Processing:
  1. get_timezone("US")
     → ismultiple_timezone=True
     → Returns list: ["America/New_York", "America/Chicago", ...]
  2. Agent asks for clarification

Bot:  "I see you're in the US. Could you let me know your timezone? 
       (e.g., Eastern, Central, Pacific)"
```

---

## Human Escalation Agent Flows

**Agent:** `human_agent` &nbsp;|&nbsp; **Tools:** `validate_email`

### Purpose
Handle graceful escalation to human support with context preservation.

### Flow 1: Standard Escalation

```
User: "I want to talk to a real person"
Processing:
  1. on_human_handoff:
     - human_requested=True
     - escalation_timestamp=ISO UTC timestamp
  2. Agent collects email for follow-up

Bot:  "I understand. Let me connect you with our team. 
       Could you share your email so someone can reach out to you directly?"

User: "john@outlook.com"
Processing:
  1. validate_email("john@outlook.com")
     → is_valid=True, typo_detected=False
  2. Email stored, ready_for_handoff=True

Bot:  "Thanks, John! A team member will reach out to you at john@outlook.com shortly. 
       Is there anything specific you'd like them to know about?"
```

### Flow 2: Email Typo Detection

```
User: "My email is john@gmial.com"
Processing:
  1. validate_email("john@gmial.com")
     → is_valid=False
     → typo_detected=True
     → suggestion="john@gmail.com"

Bot:  "Did you mean john@gmail.com? I noticed a possible typo in the domain."
```

---

## Proceed Email Agent Flows

**Agent:** `switch_to_email_agent` (used as tool by Main Agent)

### Purpose
Transition from live chat to email communication when users prefer email.

### Flow 1: Email Switch

```
User: "Can you send me the details over email?"
Processing:
  1. Main agent calls proceed_with_email tool
  2. Proceed Email agent generates email template selection

Bot:  "I'd be happy to send you the details via email! 
       What's your email address?"
```

---

## Lead Analysis Agent Flows

**Agent:** `lead_analysis_agent` (used as tool by Demo Booking Agent)

### Purpose
Classify lead quality after successful demo bookings.

### Flow 1: Post-Booking Analysis

```
[After booking is confirmed]
Processing:
  1. Demo booking agent calls lead_analysis_tool
  2. Lead Analysis agent analyzes:
     - Conversation history (engagement level)
     - Urgency signals
     - Specific product interest
     - Contact details completeness
  3. Returns LeadAnalysis:
     - lead_classification: "hot"
     - reasoning: "User showed high urgency, specific product interest, quick decision"
     - key_indicators: ["immediate need", "asked about pricing", "booked quickly"]
     - urgency_level: "immediate"
     - recommended_next_action: "Priority follow-up call within 24 hours"
```

---

## Cross-Agent Workflows

### Workflow 1: Sales → Demo Booking → Lead Analysis

**Scenario:** User inquires about products, then decides to book a demo.

```
Step 1: Main agent receives "Tell me about your AI Sales Bot"
        → Handoff to Sales Agent (on_sales_handoff: new_booking=True)

Step 2: Sales agent responds with product info using RAG
        User: "Looks great! Can I see a demo?"

Step 3: Sales agent determines intent → booking request
        → Handoff back to Main agent → Handoff to Demo Booking Agent
        (on_demo_handoff: new_booking=True)

Step 4: Demo Booking agent collects: email, timezone, date, time
        → Tools: get_timezone, process_booking_datetime, check_calendly

Step 5: Booking confirmed → lead_analysis_tool called
        → Lead classified as "hot" (engaged, booked quickly)

Step 6: State saved with:
        - booking_confirmed=True
        - contact_details populated
        - lead_details with classification
        - executive_summary generated (booking milestone)
```

### Workflow 2: Demo Booking → Cancellation → Follow-up

```
Step 1: User: "I need to cancel my demo"
        → Demo Booking Agent (booking_type="cancel")
        
Step 2: Bot: "Your demo has been cancelled. Would you like to reschedule later?"

Step 3: User: "Yeah, remind me next week"
        → Handoff to Follow-up Agent (follow_trigger=True)

Step 4: Follow-up agent schedules reminder
        → followup_details set
```

### Workflow 3: Any Agent → Human Escalation

```
Step 1: User is in conversation with any agent

Step 2: User: "This isn't helping, I need a real person"

Step 3: Current agent detects escalation intent
        → Handoff to Human Agent (human_requested=True, escalation_timestamp set)

Step 4: Human agent:
        - Summarizes conversation context
        - Collects email with validation
        - Sets ready_for_handoff=True
```

### Workflow 4: Probing → CTA → Demo Booking

```
Step 1: User interacts with Sales agent
        Enable_probing=True, probing questions configured

Step 2: Agent weaves probing questions into conversation:
        Q1: "How large is your sales team?" → answered, score +20
        Q2: "What's your current process?" → answered, score +15
        Q3: "What's your timeline?" → answered, score +20
        Total: 55 ≥ threshold(50) → probing_completed=True, can_show_cta=True

Step 3: Agent shows CTA: "Based on your needs, I think a demo would be perfect!
         Would you like to schedule one?"

Step 4: User: "Sure!" → Handoff to Demo Booking Agent
```

### Workflow 5: Probing → Objection Limit

```
Step 1: Agent asks probing question
Step 2: User objects: "I'd rather not answer that"
        → is_objection=True, objection_count incremented
Step 3: After 3 objections (default limit):
        → is_objection_limit_reached=True
        → probing_completed=True, can_show_cta=True
Step 4: Agent gracefully presents CTA without further probing
```

---

## Probing System Flows

### Score Tracking

The `ProbingEngine` in `app/core/probing.py` manages:

```
For each user response:
  1. Agent returns ProbingOutput:
     - detected_question: which question was answered
     - detected_answer: the answer
     - score_to_add: points for this answer
     - is_answered: whether it was a real answer
     - is_objection: whether user objected
     
  2. ProbingEngine.update_probing_context():
     - If is_answered: append to Q/A list, add score
     - If is_objection: increment objection counter
     - Check: total_score ≥ probing_threshold?
       → Yes: probing_completed=True, can_show_cta=True
     - Check: objection_count ≥ objection_limit?
       → Yes: probing_completed=True, can_show_cta=True
```

---

## Standalone Agent Flows

### Probing Question Generation

**Agent:** `probing_agent` &nbsp;|&nbsp; **Endpoint:** `POST /generate_probing_questions`

```
Input: BotPersona + total_k + comment
Processing:
  1. Agent receives persona context
  2. Generates total_k qualifying questions
  3. Each question includes: id, question, score, priority, mandatory flag

Output: List[ProbingQuestion]
```

### Website Crawler & Persona Auto-Fill

**Agent:** `crawl_persona_agent` &nbsp;|&nbsp; **Endpoint:** `POST /autofill_persona`

```
Input: URL, user_id, max_depth, max_pages, max_tokens

Processing:
  1. Crawl4AI deep-crawls the URL with BFS strategy
  2. Extract clean markdown from each page
  3. Skip media URLs
  4. Clean text: remove Unicode noise, normalize whitespace
  5. Trim to max_tokens
  6. Send to LLM (Gemini 3 Flash) with crawl_persona_prompt
  7. LLM returns BotPersona model
  8. Ingest crawled content into ChromaDB (user_id as collection)

Output: {pages_analyzed, urls, bot_persona: BotPersona}
```

### Instruction Generation

**Agent:** `probing_instruction_agent` &nbsp;|&nbsp; **Endpoint:** `POST /generate_instructions`

```
Input: BotPersona + max_instructions

Processing:
  1. Agent receives persona context
  2. Generates instruction suggestions for probing question creation
  3. Returns list of instruction strings

Output: {instructions: List[str]}
```

---

*For related documentation, see:*
- [ARCHITECTURE.md](ARCHITECTURE.md) — System architecture and component details
- [TOOLS_REFERENCE.md](TOOLS_REFERENCE.md) — Complete tool specifications
- [DEVELOPERS.md](DEVELOPERS.md) — How to create new agents and tools
