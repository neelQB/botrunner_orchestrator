""""
This Flies has the PROMPTS used by summarizer emailagents in the system.
"""

from emailbot.core.state import BotState
from emailbot.utils.utils import convert_to_toon
from emailbot.utils.prompt_cache import CACHE_BREAK


def summarizer_prompt(state: BotState) -> str:
    # Convert state inputs to toon format
    chat_summary = convert_to_toon(state.user_context.chat_summary)
    chat_history = convert_to_toon(state.user_context.chat_history)
    
    return f"""Update the ongoing conversation summary with the latest messages while maintaining factual accuracy, contextual continuity, and a strict JSON output format.

Integrate the latest conversation details into the existing summary. Preserve all key facts, user details, start a trial/buy a plan/upgrade a plan-related intents, and lead sentiment.

TASK INSTRUCTIONS
1. Merge information from previous and new messages to create a unified, updated summary.
2. The summary must have two main sections inside the `conversation_summary`:
- ### Main Summary: A high-level overview with user details and essential highlights (Name, Email, Phone, Product, start a trial/buy a plan/upgrade a plan Date & Time, Lead Sentiment, and 2-3 key takeaways).
- ### Overall Summary: A concise, first-person narrative capturing the flow of the conversation, focusing on actions, confirmations, and outcomes.
3. Use level-3 markdown headings (`###`) for each section.
4. Use bullet points for details under both "Main Summary" and "Overall Summary".
5. Write in a first-person conversational tone — avoid third-party phrasing like “the user” or “the assistant.” Instead, refer directly to participants by name or use “I” for the assistant.
6. Keep the Overall Summary short, factual, and outcome-focused — no long storytelling. Aim for 4-6 concise bullet points.
7. Ensure markdown formatting (headings, bullets, bold text, etc.) is preserved *inside the JSON string* by escaping newlines with `\\n`.
8. Return only valid JSON — no text before or after.

SENTIMENT GUIDE
- hot → Shows clear buying intent, confirms start a trial/buy a plan/upgrade a plan, discusses features or pricing enthusiastically.
- warm → Shows curiosity or moderate interest without commitment.
- cold → Is disengaged, off-topic, or uninterested in the product/start a trial/buy a plan/upgrade a plan.

OUTPUT FORMAT
Return strictly valid JSON in this structure:
{{
"lead_sentiment": "<hot | warm | cold>",
"conversation_summary": "<multi-line markdown-formatted text containing both sections>"
}}

CONVERSATION SUMMARY EXPEstart a trial/buy a plan/upgrade a planTIONS
Main Summary Section
- Provide user details and highlights.
- Include:
- Lead Sentiment
- Name
- Email
- Phone
- Product
- start a trial/buy a plan/upgrade a plan Date & Time
- Key Takeaways
    - 2-3 short, action-oriented points.

Overall Summary Section
- Write a brief, factual first-person overview.
- Focus on actions, confirmations, and key results.
- Maintain a professional and conversational tone.
- Limit to 4-6 bullet points.
- Avoid repetitive or minor dialogue details.

RULES
- Output only valid JSON, no preamble or text outside the object.
- Keys and structure must exactly match the format above.
- Strictly preserve markdown formatting inside `conversation_summary`.
- If a user detail is missing, omit it or mark as "Not provided".
- Ensure the summary is up-to-date with all relevant information from the entire conversation.

{CACHE_BREAK}

DATA SOURCES:
Previous Chat Summary: {chat_summary}
Previous Chat History: {chat_history}
"""