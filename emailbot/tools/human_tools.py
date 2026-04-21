"""
Tools for human escalation agent
"""

from typing import Dict, Optional, List


from emailbot.config.settings import logger
import uuid
import re
from datetime import datetime
from pydantic import BaseModel, Field
from agents import function_tool
import os
from openai import OpenAI


class ChatMessage(BaseModel):
    """Schema for chat history messages"""

    role: str
    content: str


@function_tool
def validate_email(email: str) -> Dict:
    """
    Validates email format and detects common typos.
    Args:
        email: Email address to validate
    Returns:
        Dictionary with validation result and suggestions
    """
    logger.info(f"[validate_email] Validating email: {email}")

    try:
        # Basic email regex pattern
        email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"

        # Clean email (remove spaces, convert to lowercase)
        cleaned_email = email.strip().lower()

        # Common domain typos mapping
        domain_corrections = {
            "gamil.com": "gmail.com",
            "gmial.com": "gmail.com",
            "gmai.com": "gmail.com",
            "gmil.com": "gmail.com",
            "gmaill.com": "gmail.com",
            "gmail.co": "gmail.com",
            "yahho.com": "yahoo.com",
            "yahooo.com": "yahoo.com",
            "yaho.com": "yahoo.com",
            "yahoo.co": "yahoo.com",
            "outlok.com": "outlook.com",
            "outloo.com": "outlook.com",
            "outlook.co": "outlook.com",
            "hotmial.com": "hotmail.com",
            "hotmai.com": "hotmail.com",
            "hotmail.co": "hotmail.com",
            "icloud.co": "icloud.com",
            "icould.com": "icloud.com",
            "aol.co": "aol.com",
            "live.co": "live.com",
            "protonmail.co": "protonmail.com",
            "protonmai.com": "protonmail.com",
        }

        # Check if email matches basic pattern
        if not re.match(email_pattern, cleaned_email):
            logger.warning(f"[validate_email] Invalid email format: {cleaned_email}")
            return {
                "is_valid": False,
                "email": cleaned_email,
                "error": "Invalid email format. Please check the format (e.g., user@example.com)",
                "typo_detected": False,
                "suggestion": None,
            }

        # Extract domain from email
        try:
            local_part, domain = cleaned_email.split("@")
        except ValueError:
            return {
                "is_valid": False,
                "email": cleaned_email,
                "error": "Email must contain exactly one @ symbol",
                "typo_detected": False,
                "suggestion": None,
            }

        # Check for domain typos
        if domain in domain_corrections:
            corrected_domain = domain_corrections[domain]
            suggested_email = f"{local_part}@{corrected_domain}"

            logger.info(
                f"[validate_email] Typo detected: {domain} -> {corrected_domain}"
            )
            return {
                "is_valid": False,
                "email": cleaned_email,
                "typo_detected": True,
                "suggestion": suggested_email,
                "error": f"Did you mean {suggested_email}?",
            }

        # Check for suspicious patterns
        suspicious_patterns = [
            r"\.\.",  # Double dots
            r"^\.",  # Starts with dot
            r"\.$",  # Ends with dot
            r"@.*@",  # Multiple @ symbols
            r"\s",  # Contains whitespace
        ]

        for pattern in suspicious_patterns:
            if re.search(pattern, cleaned_email):
                logger.warning(
                    f"[validate_email] Suspicious pattern detected: {pattern}"
                )
                return {
                    "is_valid": False,
                    "email": cleaned_email,
                    "error": "Email contains invalid characters or patterns",
                    "typo_detected": False,
                    "suggestion": None,
                }

        # Additional validation: Check if domain has TLD
        if "." not in domain:
            return {
                "is_valid": False,
                "email": cleaned_email,
                "error": "Email domain must have a valid extension (e.g., .com, .org)",
                "typo_detected": False,
                "suggestion": None,
            }

        # Email is valid
        logger.info(f"[validate_email] Email validated successfully: {cleaned_email}")
        return {
            "is_valid": True,
            "email": cleaned_email,
            "message": "Email format is valid",
            "typo_detected": False,
            "suggestion": None,
        }

    except Exception as e:
        logger.error(f"[validate_email] Error validating email: {e}")
        return {
            "is_valid": False,
            "email": email,
            "error": f"Validation error: {str(e)}",
            "typo_detected": False,
            "suggestion": None,
        }


# @function_tool
# def summarize_conversation(chat_history: List[ChatMessage]) -> Dict:
#     """
#     Summarizes the conversation between user and bot before human escalation.
#     Provides context about what was discussed and the current state.

#     Args:
#         chat_history: List of chat messages with 'role' and 'content' keys

#     Returns:
#         Dictionary with conversation summary and key details
#     """
#     logger.info(
#         f"[summarize_conversation] Summarizing conversation with {len(chat_history)} messages"
#     )

#     try:
#         if not chat_history or len(chat_history) == 0:
#             return {
#                 "success": False,
#                 "summary": "No conversation history available",
#                 "key_topics": [],
#                 "user_sentiment": "neutral",
#                 "messages_count": 0,
#             }

#         # Initialize OpenAI client
#         client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

#         # Format chat history for summarization
#         conversation_text = ""
#         for msg in chat_history:
#             role = (
#                 msg.role if isinstance(msg, ChatMessage) else msg.get("role", "unknown")
#             )
#             content = (
#                 msg.content if isinstance(msg, ChatMessage) else msg.get("content", "")
#             )
#             conversation_text += f"{role.upper()}: {content}\n\n"

#         # Create summarization prompt
#         summarization_prompt = f"""You are an AI assistant that summarizes customer service conversations.

# Analyze the following conversation between a user and a customer support bot, then provide:
# 1. A concise summary (2-3 sentences) of what was discussed
# 2. Key topics or issues mentioned
# 3. User's sentiment (positive/neutral/negative/frustrated)
# 4. Any unresolved issues or pending requests
# 5. Important context for a human agent taking over

# Conversation:
# {conversation_text}

# Provide your response in the following JSON format:
# {{
#     "summary": "Brief 2-3 sentence summary",
#     "key_topics": ["topic1", "topic2", ...],
#     "user_sentiment": "positive/neutral/negative/frustrated",
#     "unresolved_issues": ["issue1", "issue2", ...],
#     "important_context": "Any critical context for human agent",
#     "user_intent": "What the user is ultimately trying to achieve"
# }}"""

#         # Call OpenAI API for summarization
#         response = client.chat.completions.create(
#             model="gpt-4o-mini",
#             messages=[
#                 {
#                     "role": "system",
#                     "content": "You are a helpful assistant that summarizes customer service conversations accurately and concisely.",
#                 },
#                 {"role": "user", "content": summarization_prompt},
#             ],
#             temperature=0.3,
#             max_tokens=500,
#         )

#         # Extract and parse the response
#         summary_text = response.choices[0].message.content.strip()

#         # Try to parse JSON response
#         import json

#         try:
#             # Remove markdown code blocks if present
#             if summary_text.startswith("```json"):
#                 summary_text = (
#                     summary_text.replace("```json", "").replace("```", "").strip()
#                 )
#             elif summary_text.startswith("```"):
#                 summary_text = summary_text.replace("```", "").strip()

#             summary_data = json.loads(summary_text)
#         except json.JSONDecodeError:
#             logger.warning(
#                 "[summarize_conversation] Could not parse JSON, using text summary"
#             )
#             summary_data = {
#                 "summary": summary_text,
#                 "key_topics": [],
#                 "user_sentiment": "neutral",
#                 "unresolved_issues": [],
#                 "important_context": "",
#                 "user_intent": "",
#             }

#         logger.info(f"[summarize_conversation] Successfully summarized conversation")

#         return {
#             "success": True,
#             "summary": summary_data.get("summary", ""),
#             "key_topics": summary_data.get("key_topics", []),
#             "user_sentiment": summary_data.get("user_sentiment", "neutral"),
#             "unresolved_issues": summary_data.get("unresolved_issues", []),
#             "important_context": summary_data.get("important_context", ""),
#             "user_intent": summary_data.get("user_intent", ""),
#             "messages_count": len(chat_history),
#             "timestamp": datetime.utcnow().isoformat(),
#         }

#     except Exception as e:
#         logger.error(f"[summarize_conversation] Error summarizing conversation: {e}")
#         return {
#             "success": False,
#             "summary": f"Error generating summary: {str(e)}",
#             "key_topics": [],
#             "user_sentiment": "neutral",
#             "unresolved_issues": [],
#             "important_context": "",
#             "user_intent": "",
#             "messages_count": len(chat_history) if chat_history else 0,
#             "error": str(e),
#         }
