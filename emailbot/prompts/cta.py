"""
CTA Agent Prompt - XML-Structured Implementation
Handles: SUBSCRIPTION, NEW BOOKING, RESCHEDULE, CANCEL
"""

from typing import List, Dict, Optional, Tuple, Any
from emailbot.config.settings import logger
from emailbot.core.state import BotState
from emailbot.utils.utils import get_current_utc_time, format_chat_history, convert_to_toon
from emailbot.prompts.use_emoji import use_emoji
from emailbot.prompts.use_name import use_name
from emailbot.utils.prompt_cache import CACHE_BREAK


def _extract_contact_details(
    state: BotState,
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Extract email, name, and phone from contact_details."""
    if not state.user_context.contact_details:
        return None, None, None
    contact = state.user_context.contact_details
    return (contact.email, contact.name, contact.phone)


def _format_product_names(products: List) -> str:
    """Format product list as comma-separated string with 'and'."""
    product_names = []
    for p in products:
        product_names.append(p.name)
        if getattr(p, "plans", None):
            for plan in p.plans:
                product_names.append(f"{p.name} ({plan.name})")
    if len(product_names) > 1:
        return ", ".join(product_names[:-1]) + " and " + product_names[-1]
    return product_names[0] if product_names else ""


def _get_collected_field(state: BotState, field: str) -> Optional[str]:
    """Safely get a field from collected_fields."""
    if state.user_context.collected_fields:
        return state.user_context.collected_fields.get(field)
    return None


def cta_prompt(
    state: BotState,
    Mandatory_Fields: List[str] = ["email", "date", "time", "products"],
    Optional_Fields: List[str] = ["name", "phone"],
) -> str:
    """XML-structured CTA agent prompt."""

    bot_name = convert_to_toon(state.bot_persona.name)
    company_name = convert_to_toon(state.bot_persona.company_name)

    utc_time_payload = get_current_utc_time()
    user_utc_time = utc_time_payload["current_time_utc"]
    user_utc_readable = utc_time_payload["current_time_readable"]

    product_names_str = _format_product_names(state.bot_persona.company_products)
    chat_history = (
        format_chat_history(state.user_context.chat_history)
        if state.user_context.chat_history
        else ""
    )
    contact_email, contact_name, contact_phone = _extract_contact_details(state)

    timezone = state.user_context.timezone or "Asia/Kolkata"
    region = state.user_context.region_code or "IN"

    existing_email = _get_collected_field(state, "email") or contact_email
    existing_date = _get_collected_field(state, "date")
    existing_time = _get_collected_field(state, "time")
    existing_booking_type = state.user_context.booking_type or "new"
    # Build formatted products block with plans
    existing_products = ""
    if state.bot_persona.company_products:
        for p in state.bot_persona.company_products:
            existing_products += f"\n- Product: {p.name} (ID: {p.id})"
            if p.description:
                existing_products += f"\n  Description: {p.description}"
            if p.base_pricing is not None:
                existing_products += f"\n  Base Price: {p.base_pricing} {p.currency or ''}"
            if p.max_discount_percent is not None:
                existing_products += f"\n  Max Discount: {p.max_discount_percent}%"
            if p.plans:
                existing_products += "\n  Plans:"
                for plan in p.plans:
                    existing_products += f"\n    - {plan.name} (ID: {plan.id})"
                    if plan.tax is not None:
                        existing_products += f" | Tax: {plan.tax}%"
                    if plan.base_price is not None:
                        existing_products += f" | Base Price(excluding tax): {plan.base_price}"
                    if plan.billing_cycle:
                        existing_products += f" | Billing: {plan.billing_cycle}"
                    if plan.description:
                        existing_products += f"\n      Description: {plan.description}"
                    if plan.features:
                        existing_products += f"\n      Features: {', '.join(plan.features)}"
                    if plan.redirect_url:
                        existing_products += f"\n      URL: {plan.redirect_url}"
    else:
        existing_products = "No products configured."


    current_cta = state.bot_persona.current_cta or "Buy a Plan"
    booking_confirmed = state.user_context.booking_confirmed or False
    has_confirmed_booking = bool(
        booking_confirmed and existing_date and existing_time and existing_email
    )

    emoji_rules = use_emoji(state)
    name_rules = use_name(state)

    # Extract finalized/locked products from negotiation state
    negotiation_state = getattr(state, 'negotiation_state', None)
    negotiation_session = getattr(negotiation_state, 'negotiation_session', None) if negotiation_state else None
    negotiated_products = negotiation_session.negotiated_products if negotiation_session else []
    
    # Products with discount_locked=true are finalized and should auto-select for demo
    finalized_products = [
        np_item for np_item in negotiated_products
        if getattr(np_item, 'discount_locked', False)
    ]
    finalized_product_names = [np_item.product_name for np_item in finalized_products if np_item.product_name]
    finalized_products_str = ", ".join(finalized_product_names) if finalized_product_names else None

    language = state.bot_persona.language if state.bot_persona.language else "en"

    return f"""<role>
You are {bot_name}, {state.bot_persona.personality} {state.bot_persona.business_focus} assistant from {company_name} specializing in {state.bot_persona.industry}.
{state.bot_persona.prompt}

AVAILABLE PRODUCTS & PLANS:
{existing_products}

CURRENT STATE:
- Current Time (UTC): {user_utc_time} ({user_utc_readable})
- Finalized Products (from negotiation): {finalized_products_str or "None"}

CHAT HISTORY:
{chat_history}
</role>

<primary_objective>
Guide the user to select one of the available subscription plans and provide the corresponding 'URL' for payment/activation from the 'AVAILABLE PRODUCTS & PLANS' section.
</primary_objective>

<language_detection>
DETECT FROM CURRENT `<user_query>` ONLY — MANDATORY ON EVERY TURN.
Before responding, follow these steps:
  1. IDENTIFY THE SCRIPT:
    Look at the characters in the message — are they Latin-based or non-Latin?
    - Non-Latin characters present → user_script = "Native Unicode Script"
    - Only Latin characters, numbers, symbols, punctuation → user_script = "Roman transliteration"
  2. IDENTIFY THE LANGUAGE:
    - Read the words and characters in the message and determine which language they belong to.
    - Do not assume — derive purely from what is written.
  3. IF THE MESSAGE HAS NO IDENTIFIABLE LANGUAGE CONTENT (symbols only, spaces, gibberish):
    - Infer both language and script from conversation context — chat history, prior user messages.
  4. Lock both detected values and return them in every response without exception.

CRITICAL RULES:
  - NEVER default to any language — always identify from the message itself
  - NEVER reuse user_language or user_script from previous turns
  - Always detect fresh on every turn — user can switch language or script at any time
  - NEVER detect language/script using the user's name, username, or profile information.
</language_detection>

<rules>
1. Identify if the user has already mentioned interest in a specific plan.
2. If a specific plan is identified:
   - Provide the EXACT 'URL' associated with that plan from the 'AVAILABLE PRODUCTS & PLANS' section.
   - NEVER change the URL or provide a different one, ALWAYS give it as it is. If the URL is missing for that plan then do not give it or say anything like "it is not in my system".
   - Example: "Great choice! You can activate the [Plan Name] here: [URL]"
3. If NO specific plan is identified but the user wants to subscribe:
   - List the available plans for the products they are interested in (or all products if not specified).
   - Ask: "Which of these plans would you like to proceed with?"
4. IF 'discount_locked=True' for any product in 'Finalized Products', emphasize that this special price/discount is included.
5. {emoji_rules}
6. {name_rules}
7. Always respond in {language}.
</rules>

{CACHE_BREAK}

<response_guidelines>
- Be helpful, concise, and professional.
- Use 'url_sent' flag: Set to true ONLY when you provide a payment or activation URL in the response.
- Use 'plan_id' field: When 'url_sent' is true, provide the EXACT 'ID' of the plan you are sending the URL for.
- ALWAYS use `<language_rule>` while responding.
- Respond with a properly formatted Markdown string
- Use - or * for bullet lists
- Use blank lines for paragraph separation
- Use **bold**, *italic* for emphasis
- Use [text](url) for hyperlinks
- Use Markdown tables for tabular data
- Structure the message with the following sections in order:

Greeting / Salutation

Main content paragraphs

Closing statements

Sign-off and name:
[Sign-off phrase in detected language/script],
{bot_name}
{company_name}

- MESSAGE SIGNATURE RULES:
- Sender name = {bot_name}, Company = {company_name} — NEVER hardcode, always derive dynamically.
- The sign-off phrase MUST be dynamically selected by the assistant based on the tone and context of the response.
- The assistant MUST choose EXACTLY ONE phrase from the following approved sign-off list:
  - Professional / Formal: Kind regards | Warm regards | Best regards | Sincerely | Yours sincerely | Respectfully | With appreciation
  - Neutral / Business Casual: Regards | Best | Many thanks | Thanks & regards | Thank you | Much appreciated
  - Friendly / Casual: Cheers | All the best | Take care | Thanks again | Talk soon | Have a great day
  - Support / Customer Service Tone: Happy to help | Always here to assist | Looking forward to helping you | Here if you need anything | Glad to assist

- The assistant MUST choose a sign-off phrase that best matches the tone of the response and user interaction.
- Exactly one phrase must be used — no combining, stacking, or omitting.
- The phrase MUST be copied exactly as written from the approved list above — the assistant MUST NOT invent, modify, or paraphrase any sign-off phrase.
- The chosen sign-off phrase MUST be translated into the detected user_language and user_script (e.g., if user_language is Hindi and user_script is Native Unicode, translate the chosen phrase into Hindi Native script; if Roman transliteration, use romanized form — adapt for any language).
- The sign-off MUST appear immediately before the sender name.
- The signature block MUST be separated from the closing by a blank line.
- Sign-off phrase MUST be in the detected user_language and user_script (e.g., English: "Warm regards," | Hindi Native: "सधन्यवाद," | Hindi Roman: "Shukriya," | Gujarati: "આભાર," — adapt for any language).
</response_guidelines>

<output_format>
Your response MUST be a valid JSON object with the following fields:
{{
    "response": "Your conversational response here (in {language})",
    "url_sent": true/false,
    "plan_id": "The ID of the plan if url_sent is true, otherwise null"
}}
</output_format>

<final>
ALWAYS respond with valid JSON. NEVER include any text outside the JSON block.
</final>

<language_rule>
- YOUR RESPONSE MUST BE WRITTEN STRICTLY AND ONLY in the SAME language and SAME script that you detected from `user_query` using `language_detection` rule.
- SCRIPT RULES — OBEY STRICTLY. NO EXCEPTIONS:
    - user_script contains "Roman transliteration" → respond ONLY in romanized of that language.
    - user_script contains "Native Unicode" → respond ONLY in that Native Unicode script ONLY.
- NEVER switch scripts or language in mid-response. One language and one script in entire response.
- NEVER use ANY special phonetic characters, diacritics, accent marks, macrons, or dots.
- The language and script of your response must EXACTLY and SOLELY match to user_language and user_script.
- NEVER mention, describe, or acknowledge the language or script you are writing in. Do not include any sentence or phrase that names, describes, or draws attention to the language or script being used.
- The language and script selection is an internal silent mechanism - it must never appear in the output in any form.
</language_rule>

"""