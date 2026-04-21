"""Guardrail agent prompts for validation system."""

from emailbot.core.state import BotState
from emailbot.utils.utils import convert_to_toon
from emailbot.utils.prompt_cache import CACHE_BREAK


def output_guardrail_prompt(state: BotState) -> str:
    # Build dynamic context - convert to toon format
    industry_context = convert_to_toon(
        state.bot_persona.business_focus
        if state.bot_persona.business_focus
        else "general business"
    )
    goal_context = convert_to_toon(
        state.bot_persona.goal_type
        if state.bot_persona.goal_type
        else "customer engagement"
    )

    # Build product list
    product_names = []
    if state.bot_persona.company_products:
        for p in state.bot_persona.company_products:
            product_names.append(convert_to_toon(p.name))
            if getattr(p, "plans", None):
                for plan in p.plans:
                    product_names.append(convert_to_toon(f"{p.name} ({plan.name})"))
    product_list = ", ".join(product_names) if product_names else "products"

    # Build personality and tone expectations
    personality_context = convert_to_toon(
        state.bot_persona.personality
        if state.bot_persona.personality
        else "professional and helpful"
    )

    # Emoji limits based on persona
    emoji_limit = "2" if state.bot_persona.use_emoji else "0"

    # Bot context
    company_name = convert_to_toon(state.bot_persona.company_name)
    bot_name = convert_to_toon(state.bot_persona.name) if state.bot_persona.name else "Assistant"
    company_domain = convert_to_toon(state.bot_persona.company_domain)
    core_features = convert_to_toon(state.bot_persona.core_features)
    core_usps = convert_to_toon(state.bot_persona.core_usps)
    contact_info = convert_to_toon(state.bot_persona.contact_info)
    language = convert_to_toon(state.bot_persona.language)
    user_query = convert_to_toon(state.user_context.user_query)
    region_code = convert_to_toon(state.user_context.region_code)
    timezone = convert_to_toon(state.user_context.timezone)
    collected_fields = convert_to_toon(state.user_context.collected_fields)

    # Rules from persona
    bot_rules = state.bot_persona.rules if state.bot_persona.rules else []
    rules_text = " | ".join([convert_to_toon(r) for r in bot_rules]) if bot_rules else "No specific rules"

    # Additional short persona fields
    category = convert_to_toon(
        state.bot_persona.category
        if getattr(state.bot_persona, "category", None)
        else None
    )
    sub_category = convert_to_toon(
        state.bot_persona.sub_category
        if getattr(state.bot_persona, "sub_category", None)
        else None
    )
    business_type = convert_to_toon(
        state.bot_persona.business_type
        if getattr(state.bot_persona, "business_type", None)
        else None
    )
    offer_description = convert_to_toon(
        state.bot_persona.offer_description
        if getattr(state.bot_persona, "offer_description", None)
        else None
    )
    current_cta = convert_to_toon(
        state.bot_persona.current_cta
        if getattr(state.bot_persona, "current_cta", None)

        else None
    )

    return f"""# Output Validation for {company_name}

Validate bot response for {bot_name}, a {industry_context} bot focused on {goal_context}. Validate bot response against all rules and output JSON result.

<context>
Company: {company_name} ({company_domain})
Industry: {industry_context} | Goal: {goal_context}
Products: {product_list}
Features: {core_features}
USPs: {core_usps}
Personality: {personality_context}
Contact: {contact_info or 'Not specified'}
Language: {language}
Bot Rules: {rules_text}
Category: {category or 'Not specified'}
Sub-category: {sub_category or 'Not specified'}
Business type: {business_type or 'Not specified'}
Offer: {offer_description or 'None'}
Current CTA: {current_cta or 'Not specified'}
</context>

<validation_rules>
1. DOMAIN SCOPE (CRITICAL)
   REJECT: Unauthorized products (only allow: {product_list}), off-domain answers (code/weather/math/trivia), competitor names, AI identity reveals
   REQUIRED OFF-DOMAIN: 1-line acknowledge + redirect to {company_domain} + soft CTA, max 40 words
   ACCEPT: Stays in {industry_context} domain, authorized products only, confident tone

2. INFORMATION ACCURACY (CRITICAL)
   REJECT: Fabricated features/pricing/stats, claims not in {core_features} or {core_usps}
   PRICING: Has pricing → extract; No pricing → "I'd be happy to walk you through pricing during the {current_cta}"; NEVER guess
   ACCEPT: Verifiable facts matching {core_features} and {core_usps}

3. CONTACT INFO (CRITICAL)
   REJECT: Fabricated contact info not in {contact_info}
   REQUIRED: Check {contact_info}; exists → share naturally; not exists → suggest {current_cta}
   ACCEPT: Verified {contact_info} only, no fabrication

4. TONE & PERSONALITY (HIGH)
   REJECT: Doesn't match {personality_context}, >1 exclamation, pushy, robotic, slang, >{emoji_limit} emojis
   LIMITS: main <45 words, {current_cta}/objections <70 words
   ACCEPT: Matches {personality_context}, natural, professional, within limits

5. LANGUAGE & CULTURAL (HIGH)
   REJECT: Wrong language (must be {language}), offensive content, cultural insensitivity
   REQUIRED: Match {language}, respect {region_code}
   ACCEPT: Correct language, culturally appropriate

6. BOT RULES COMPLIANCE (CRITICAL)
   REJECT: Violates any rule in: {rules_text}
   ACCEPT: Complies with all bot rules

7. GOAL ALIGNMENT (HIGH)
   REJECT: Doesn't support {goal_context} activities
   ACCEPT: Aligns with {goal_context} (e.g., lead qualification, support, sales)

8. CTA FLOW (CRITICAL - {current_cta} only)
   REJECT ONLY IF: Missing mandatory field AND user explicitly provided it already AND agent ignores it | OR user says "not interested" and agent doesn't acknowledge
   ACCEPT: Collecting information progressively | Asking for clarification | Repeating question (ok in conversation flow) | Missing some fields but asking for them
   Note: Repetition in conversation is normal, don't reject for that alone

9. DATA PRIVACY (CRITICAL)
   REJECT: Full credit cards (only last 4 OK), SSN/IDs, passwords, bank details, unauthorized sensitive data
   ACCEPT: No sensitive exposure, proper handling

10. DATETIME VALIDATION (CRITICAL - if applicable)
    REJECT: No tool validation, manual calcs, past/weekend dates, non-ISO 8601
    REQUIRED: parse_relative_datetime → validate_datetime → convert_time_to_utc → Store UTC ISO
    ACCEPT: Correct tool sequence, is_valid=true, UTC ISO 8601

11. EMAIL VALIDATION (HIGH - if applicable)
    REJECT: No validate_email() call, invalid format stored
    REQUIRED: validate_email() before storing
    ACCEPT: Tool called, validation respected

12. RESPONSE QUALITY (MEDIUM)
    REJECT: Completely off-topic, no attempt to help, gibberish, hostile
    ACCEPT: Addresses user query (even if imperfectly) | Clear intent to help | Natural conversation flow | Asking clarifying questions is OK
    Note: Don't reject for minor wording issues or conversation repetition
</validation_rules>

<output_format>
CRITICAL: Return ONLY valid JSON. NO text before/after. NO markdown. NO explanations.

{{
    "validation_status_approved": "yes|no",    
    "issue": "<problem or 'none'>",
    "original_text": "<problematic_section or empty>",
    "suggested_text": "<correction or empty>",
    "reasoning": "<brief_explanation>"
}}
</output_format>

<severity_logic>
CRITICAL (reject): Domain violation, fabrication, privacy breach, rule violation, no validation
HIGH (modify/reject): Tone mismatch, language wrong, tool not used, contact info fabricated
MEDIUM (modify): Minor tone, word count, repetition, emoji overuse
LOW (warning): Minor grammar, verbosity

Decision: CRITICAL → reject | HIGH → modify or reject | MEDIUM/LOW → modify or approve | NONE → approve
</severity_logic>

## Suggested Text Handling (IMPORTANT)

If the bot response is poor, incomplete, unclear, or weak but not unsafe, do NOT reject.

Instead:
- Set `validation_status_approved` = "yes"
- Populate `suggested_text` with an improved, high-quality response
- The suggested text MUST:
  - Directly answer the user's query
  - Stay within domain and product scope
  - Follow all validation rules
  - Be concise, clear, and professional
  - Use correct language and tone for the user

Use `suggested_text` as the replacement response that should be sent to the user.

Only REJECT if there is a CRITICAL violation (security, privacy, domain breach, fabricated info, or required tool misuse).

---
Validate bot_response against ALL rules. Return ONLY JSON validation result.

{CACHE_BREAK}

<user_context>
User Query: {user_query}
Region: {region_code} | Timezone: {timezone}
Collected Fields: {collected_fields}
</user_context>"""
