"""
This module contains utility functions for the runner application.
"""



import re
import html
import json
from toon import encode
from typing import List, Dict, Any

from datetime import datetime, UTC
from dataclasses import is_dataclass, asdict
from emailbot.core.state import BotState, BotRequest

from emailbot.config.settings import logger
from emailbot.config import settings

# convert_to_toon
def convert_to_toon(data):
    try:
        # Handle None and simple scalar types directly — toon.encode()
        # expects dict-like structures and will fail with AttributeError
        # ("'str' object has no attribute 'items'") on primitives.
        if data is None:
            return ""
        if isinstance(data, (str, int, float, bool)):
            return data
 
        # Sanitize data: convert Pydantic models to dicts
        sanitized_data = model_to_dict(data)
        json_data = json.loads(json.dumps(sanitized_data, default=str))
        return encode(json_data)
    except Exception as e:
        logger.error(f"Error converting to toon: {e}", exc_info=True)
        raise

# get_current_utc_time
def get_current_utc_time():
    try:
        now = datetime.now(UTC)
        return {
            "current_time_utc": now,
            "current_time_readable": now.strftime("%Y-%m-%d %H:%M:%S UTC"),
        }
    except Exception as e:
        logger.error(f"Error getting current UTC time: {e}", exc_info=True)
        raise

# format_chat_history
def clean_chat_history(chat_history: List[Dict[str, Any]]) -> str:
    try:
        chat_history = list(reversed(chat_history))

        grouped_output = []
        pair_index = 1
        temp_pair = []

        for msg in chat_history:
            role = msg.get("role", "").strip().lower()
            content = msg.get("content", "").strip()

            if role in ["ai", "assistant", "bot"]:
                display_role = "Assistant"
            elif role in ["human", "user"]:
                display_role = "User"
            else:
                display_role = role.capitalize()

            temp_pair.append(f"- **{display_role}**: {content}")

            # Once we have User+AI OR AI+User pair, push and reset
            if len(temp_pair) == 2:
                grouped_output.append(f"{pair_index}.\n" + "\n".join(temp_pair))
                temp_pair = []
                pair_index += 1

        # If an odd message remains (e.g., conversation ended without AI reply)
        if temp_pair:
            grouped_output.append(f"{pair_index}.\n" + "\n".join(temp_pair))

        return "\n\n".join(grouped_output)
    except Exception as e:
        logger.error(f"Error formatting chat history: {e}", exc_info=True)
        return "" # Return empty string on failure to avoid breaking UI

def format_chat_history(history: List[Dict[str, Any]]) -> str:
    """
    Format chat history for inclusion in prompts and remove HTML tags.
    """
    if not history:
        return "No previous conversation."

    chat_history = clean_chat_history(history)
    chat_history = re.sub(r"<[^>]*>", "", chat_history)
    chat_history = re.sub(r"\s+", " ", chat_history).strip()
    return chat_history

def clean_user_query(query: str) -> str:
    """
    Clean an incoming user query by stripping HTML tags, decoding HTML entities,
    and normalizing whitespace into a plain clear string.

    Steps:
    1. Decode HTML entities (e.g., &amp; -> &, &lt; -> <, &#39; -> ')
    2. Remove all HTML/XML tags (e.g., <div>, <br/>, <p class="x">)
    3. Collapse multiple whitespace characters (spaces, tabs, newlines) into single spaces
    4. Strip leading/trailing whitespace

    Args:
        query: Raw user query string, potentially containing HTML formatting.

    Returns:
        Cleaned plain-text string ready for the AI pipeline.

    Examples:
        >>> clean_user_query("<div><p>Hello <b>world</b></p></div>")
        'Hello world'
        >>> clean_user_query("Price &amp; details for &lt;Product A&gt;")
        'Price & details for <Product A>'
        >>> clean_user_query("<br/>Book a demo<br/><br/>tomorrow 5pm")
        'Book a demo tomorrow 5pm'
        >>> clean_user_query("")
        ''
    """
    if not query or not isinstance(query, str):
        return query or ""

    try:
        cleaned = query

        # Step 1: Decode HTML entities (e.g., &amp; -> &, &lt; -> <, &#39; -> ')
        cleaned = html.unescape(cleaned)

        # Step 2: Replace <br>, <br/>, <br /> tags with a space (to preserve word boundaries)
        cleaned = re.sub(r"<br\s*/?\s*>", " ", cleaned, flags=re.IGNORECASE)

        # Step 3: Remove all remaining HTML/XML tags
        cleaned = re.sub(r"<[^>]+>", "", cleaned)

        # Step 4: Collapse multiple whitespace characters into a single space
        cleaned = re.sub(r"\s+", " ", cleaned)

        # Step 5: Strip leading/trailing whitespace
        cleaned = cleaned.strip()

        if cleaned != query:
            logger.info(
                f"[QueryCleaner] Cleaned query: '{query[:80]}...' -> '{cleaned[:80]}...'"
                if len(query) > 80
                else f"[QueryCleaner] Cleaned query: '{query}' -> '{cleaned}'"
            )

        return cleaned

    except Exception as e:
        logger.error(f"[QueryCleaner] Error cleaning query: {e}", exc_info=True)
        # Return original query on error to avoid breaking the pipeline
        return query



# model_to_dict
def model_to_dict(obj) -> dict:
    """
    Recursively convert Pydantic models or dataclass instances to dictionaries.
    Handles nested models, dataclasses, and lists.
    """
    try:
        # Pydantic models
        if hasattr(obj, "model_dump"):
            return obj.model_dump()
        # Dataclasses (backward compatibility)
        elif is_dataclass(obj) and not isinstance(obj, type):
            return asdict(obj)
        elif isinstance(obj, list):
            return [model_to_dict(item) for item in obj]
        elif isinstance(obj, dict):
            return {key: model_to_dict(value) for key, value in obj.items()}
        else:
            return obj
    except Exception as e:
        logger.error(f"Error converting model to dict: {e}", exc_info=True)
        raise

# is_meaningful
def is_meaningful(val) -> bool:
    """
    Check if a value is meaningful (not None, not default 'string', not empty list/dict).
    Recursively checks dictionaries, Pydantic models, and dataclasses.
    """
    try:
        if val is None:
            return False
        if isinstance(val, str):
            return val.lower().strip() not in ["string", "", "none"]
        if isinstance(val, (list, tuple)):
            # For chat_history or other lists, ensure at least one element is meaningful
            return any(is_meaningful(i) for i in val)
        if isinstance(val, dict):
            # Special case for chat messages: must have meaningful role and content
            if "role" in val and "content" in val:
                return is_meaningful(val["role"]) and is_meaningful(val["content"])
            return any(is_meaningful(v) for v in val.values())
        # Pydantic models
        if hasattr(val, "model_dump"):
            return is_meaningful(val.model_dump())
        # Dataclasses (backward compatibility)
        if hasattr(val, "__dataclass_fields__"):
            return is_meaningful(asdict(val))
        return True
    except Exception as e:
        logger.error(f"Error checking if value is meaningful: {e}", exc_info=True)
        return False

# convert_to_botstate
def convert_to_botstate(fastapi_request: BotRequest) -> BotState:
    """
    Convert FastAPI request to BotState dataclass.
    Directly updates the session state with meaningful fields from the request.
    """
    try:
        from emailbot.database.session_manager import get_or_create_session # Local import to avoid circular dependency if any

        user_id = fastapi_request.user_context.user_id
        logger.info(f"[mainrunner] Processing request for user_id={user_id}")

        # Get or create session state
        state = get_or_create_session(user_id)

        # Update BotPersona - use UI persona if provided, otherwise fallback to default
        if fastapi_request.bot_persona is not None:
            state.bot_persona = fastapi_request.bot_persona
        # else:
        #     state.bot_persona = create_default_persona()

        # update if the field is present in the request
        existing_ctx = state.user_context
        sent_request = fastapi_request.model_dump(exclude_unset=True)
        sent_data = sent_request.get("user_context", {})

        state.user_context.user_query = fastapi_request.user_context.user_query

        for field_name, val in sent_data.items():
            if field_name == "user_query":
                continue

            if is_meaningful(val):
                # collected_fields merge
                if field_name == "collected_fields":
                    existing_ctx.collected_fields = {
                        **(existing_ctx.collected_fields or {}),
                        **val,
                    }
                    logger.info(f"[mainrunner] Merged {field_name}")

                #  dictionaries or nested structures
                elif isinstance(val, dict):
                    nested_existing = getattr(existing_ctx, field_name)
                    if nested_existing is None:
                        filtered_dict = {k: v for k, v in val.items() if is_meaningful(v)}
                        if filtered_dict:
                            setattr(existing_ctx, field_name, filtered_dict)
                            logger.info(
                                f"[mainrunner] Initialized dict field: {field_name}"
                            )
                    else:
                        #  merge of keys
                        for k, v in val.items():
                            if is_meaningful(v):
                                if isinstance(nested_existing, dict):
                                    nested_existing[k] = v
                                else:
                                    setattr(nested_existing, k, v)
                    logger.info(f"[mainrunner] Updated/Merged keys in: {field_name}")

                # Default: Direct update for scalars (bool, int, etc.) or lists
                else:
                    setattr(existing_ctx, field_name, val)
                    logger.info(f"[mainrunner] Updated field: {field_name}")
        return state
    except Exception as e:
        logger.error(f"Error converting to botstate: {e}", exc_info=True)
        raise

# get_consumption_info (replaces get_individual_token_usage)
def get_consumption_info(raw_responses, agent_name=None, primary_model=None, tags=None)->dict:
    """
    Extract rich consumption metadata per response from agent raw_responses.

    Includes model name, agent name, tags, timestamp, and per-call
    token breakdowns alongside aggregated totals and individual stage consumption.

    Args:
        raw_responses (list): result.raw_responses from agent execution
        agent_name (str, optional): Name of the last agent that handled the request
        primary_model (str, optional): Configured primary model name from settings
        tags (list[str], optional): Operational tags (e.g. ["sales", "probing"])

    Returns:
        dict: JSON-serializable consumption info summary
    """
    try:
        consumption = {
            "request_timestamp": datetime.now(UTC).isoformat(),
            "agent_name": agent_name,
            "primary_model": primary_model,
            "tags": tags,
            "responses": [],
            "individual_consumption": {},
            "totals": {
                "input_tokens": 0,
                "output_tokens": 0,
                "cached_tokens": 0,
                "total_tokens": 0,
            },
        }

        # Tracking index for different stages
        # Note: agents-sdk order is usually: [Input Guardrail, Main Agent/Specialized Agent, Output Guardrail]
        # This is a heuristic for stage mapping if stage names aren't directly available in response
        stage_mapping = {
            0: agent_name or "main_agent",
            1: "input_guardrail",
            2: "output_guardrail"
        }

        for idx, response in enumerate(raw_responses):
            usage = getattr(response, "usage", None)
            if not usage:
                continue

            # Support both agents SDK format (input_tokens/output_tokens)
            # and raw litellm format (prompt_tokens/completion_tokens) — e.g. from summarizer.
            input_tokens = (
                getattr(usage, "input_tokens", None)
                or getattr(usage, "prompt_tokens", None)
                or 0
            )
            output_tokens = (
                getattr(usage, "output_tokens", None)
                or getattr(usage, "completion_tokens", None)
                or 0
            )
            total_tokens = getattr(usage, "total_tokens", None) or (input_tokens + output_tokens)

            cached_tokens = 0
            # agents SDK path
            if getattr(usage, "input_tokens_details", None):
                cached_tokens = getattr(usage.input_tokens_details, "cached_tokens", 0) or 0
            # litellm path: prompt_tokens_details.cached_tokens
            elif getattr(usage, "prompt_tokens_details", None):
                cached_tokens = getattr(usage.prompt_tokens_details, "cached_tokens", 0) or 0

            # Extract model name: prefer explicitly-tagged actual model name (set by guardrail
            # collectors), then fall back to response.model (which may be a router alias or
            # the primary model string), and finally to primary_model as a last resort.
            model_name = (
                getattr(response, "_actual_model_name", None)
                or getattr(response, "model", None)
                or primary_model
            )
                
            # Check for explicit stage name tagged on the response object
            stage = getattr(response, "_stage_name", None)
            if not stage:
                stage = stage_mapping.get(idx, f"unknown_stage_{idx}")

            # Detect if this LLM response generated tool calls — if so, refine the stage name
            # so that tool-calling costs are broken out separately from the pure agent reasoning cost.
            # The agents SDK puts output items in response.output as objects with a .type attribute.
            # type="function_call" means the model decided to invoke a tool.
            output_items = getattr(response, "output", None) or []
            tool_names_in_response = []
            for item in output_items:
                item_type = getattr(item, "type", None) or (item.get("type") if isinstance(item, dict) else None)
                if item_type in ("function_call", "tool_use"):
                    tool_name = getattr(item, "name", None) or (item.get("name") if isinstance(item, dict) else None)
                    if tool_name:
                        tool_names_in_response.append(tool_name)

            if tool_names_in_response:
                # Label this response as a tool-call decision round
                # Use comma-joined tool names if multiple tools were called in one shot
                tools_label = ",".join(tool_names_in_response)
                stage = f"{stage}:tool:{tools_label}"

            response_data = {
                "response_index": idx,
                "model_name": model_name,
                "stage_name": stage,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cached_tokens": cached_tokens,
                "total_tokens": total_tokens,
            }

            consumption["responses"].append(response_data)
            
            # Populate individual_consumption for consistent JSON structure
            # If the same stage appears multiple times, aggregate the tokens
            if stage in consumption["individual_consumption"]:
                consumption["individual_consumption"][stage]["input"] += input_tokens
                consumption["individual_consumption"][stage]["output"] += output_tokens
                consumption["individual_consumption"][stage]["cache"] += cached_tokens
                consumption["individual_consumption"][stage]["total"] += total_tokens
                # Keep the first model name seen for the stage if multiple calls use different ones (unlikely but safe)
                if not consumption["individual_consumption"][stage].get("model_name"):
                    consumption["individual_consumption"][stage]["model_name"] = model_name
            else:
                consumption["individual_consumption"][stage] = {
                    "model_name": model_name,
                    "input": input_tokens,
                    "output": output_tokens,
                    "cache": cached_tokens,
                    "total": total_tokens,
                }

            # Aggregate totals
            consumption["totals"]["input_tokens"] += input_tokens
            consumption["totals"]["output_tokens"] += output_tokens
            consumption["totals"]["cached_tokens"] += cached_tokens
            consumption["totals"]["total_tokens"] += total_tokens

        return consumption

    except Exception as e:
        logger.error(f"Error getting token usage: {e}")
        return {}

# Backward-compatible alias (deprecated)
def get_individual_token_usage(state, result,latest_agent)->dict:
    try:
        # Router alias → real model name map — used as a SAFETY NET only.
        # route.py now tags `_actual_model_name` on every LiteLLMModelResponse
        # before it is returned, using ret.model (the true API model name).
        # This map resolves aliases for any response that slipped through without
        # being tagged (e.g. responses from older code paths or external callers).
        _ROUTER_ALIAS_MAP: dict[str, str] = {
            "primary":            settings.primary_model,
            "guardrail":          settings.guardrail_model,
            "summarizer":         settings.summarizer_model,
            "fallback-primary":   settings.openai_fallback_primary_model,
            "fallback-guardrail": settings.openai_fallback_guardrail_model,
            "fallback-summarizer":settings.openai_fallback_summarizer_model,
            "fallback-gemini":    settings.gemini_fallback_model,
        }

        for i, resp in enumerate(result.raw_responses):
            if not getattr(resp, "_stage_name", None):
                # Heuristic: the first call in the main runner is typically the starting agent (main_agent).
                # If there are multiple responses, and the final agent is specialized (e.g. sales_agent),
                # the first one is the decision-making step of the main_agent.
                if i == 0 and len(result.raw_responses) > 1:
                    setattr(resp, "_stage_name", "main_agent")
                else:
                    # For a single response, latest_agent IS the stage name.
                    # For subsequent responses in a chain, we attribute them to the landing agent.
                    setattr(resp, "_stage_name", latest_agent or "main_agent")

            # Model name resolution — priority order:
            #   1. `_actual_model_name` already set by context var in route.py (preferred — real API model)
            #   2. Alias resolution via _ROUTER_ALIAS_MAP (safety net)
            #   3. resp.model as-is if not a known alias (legacy)
            #   4. settings.primary_model as absolute last resort
            if not getattr(resp, "_actual_model_name", None):
                resp_model = getattr(resp, "model", None) or ""
                resolved = _ROUTER_ALIAS_MAP.get(resp_model)
                if resolved:
                    actual = resolved
                    logger.debug(
                        f"[consumption] Safety-net resolved alias '{resp_model}' → '{actual}'"
                    )
                elif resp_model:
                    actual = resp_model
                else:
                    actual = settings.primary_model
                setattr(resp, "_actual_model_name", actual)

        all_raw_responses = []
        # Try to put input guardrails first in the list if possible for logical order
        input_guards = [r for r in state.additional_raw_responses if getattr(r, "_stage_name", None) == "input_guardrail"]
        output_guards = [r for r in state.additional_raw_responses if getattr(r, "_stage_name", None) == "output_guardrail"]
        others = [r for r in state.additional_raw_responses if getattr(r, "_stage_name", None) not in ["input_guardrail", "output_guardrail"]]
        
        all_raw_responses.extend(input_guards)
        all_raw_responses.extend(result.raw_responses)
        all_raw_responses.extend(output_guards)
        all_raw_responses.extend(others)

        consumption = get_consumption_info(
            raw_responses=all_raw_responses,
            agent_name=latest_agent,
            primary_model=settings.primary_model,
            tags=[latest_agent] if latest_agent else None,
        )
        return consumption
    except Exception as e:
        logger.error(f"Error getting individual token usage: {e}")
        return {}
    
    # sanitize_response
def sanitize_response(text: str) -> str:
    """
    Remove markdown formatting and em dashes from agent responses.
    
    Removes:
    - Double asterisks (**) used for bold formatting
    - Em dashes (—) and en dashes (–)
    - Hash symbols (#) used for markdown headers
    Args:
        text: The response text to sanitize
        
    Returns:
        Sanitized response text
    """
    if not text or not isinstance(text, str):
        return text
    
    # Remove double asterisks (bold markdown)
    text = text.replace("**", "*")
    
    # Remove em dashes (—) and en dashes (–)
    text = text.replace("—", "–")

    # Remove hash symbols (markdown headers)
    text = text.replace("#", "")
    
    return text