"""
Application Agent Module - Main entry point for chatbot execution.

This module provides the core chatbot functionality including:- Agent execution via Runner
- Response finalization and history management
- Integration with caching, summarization, and executive summaries

Usage:
    from app_agent import run_emailbot_api, create_bot_state
    
    state = create_bot_state(user_id="123", user_query="Hello")
    result_state = await run_emailbot_api(state)
    print(result_state.response)
"""

import asyncio
import os
import uuid 
import json
import re as _re
import litellm

from typing import Any, Dict, List, Optional
from agents import (
    RunContextWrapper,
    Runner,
    RunConfig,
    SQLiteSession,
    set_trace_processors,
)
from agents.exceptions import OutputGuardrailTripwireTriggered, InputGuardrailTripwireTriggered
from colorama import Fore, Style
from emailbot.config.settings import Settings, logger
from openai import OpenAI
from opik import track, opik_context

# Import from new modular structure
from emailbot.config import settings, MAX_HISTORY
from emailbot.core.models import (
    UserContext,
    BotPersona,
    BotState,
    ContactDetails,
    Products,
    BotResponse,
    NegotiationState,
    NegotiationAgentResponse,
    NegotiatedProduct,
    ConsumptionInfo,
)
from emailbot.core.exceptions import (
    AgentExecutionError,
    StateError,
    GuardrailError,
)
from emailbot.core.probing_state import ProbingEngineState
from emailbot.core.negotiation import NegotiationEngine

# Import agent factory
from emailbot.emailagents.factory import root_agent

# Database imports (not modified per requirements)
from emailbot.database.session_manager import init_memory_db, save_state

from emailbot.database.cachememory import (
    get_session,
    init_session,
    update_session,
    retrieve_from_cache,
)
from emailbot.utils.prompt_cache import cache_monitor
from emailbot.utils.utils import get_individual_token_usage, clean_user_query
from emailbot.utils.response_formatting import markdown_to_html_div, html_div_to_markdown
from emailbot.database.agent_session import get_agent_session, dispose_engine


# # Initialize OpenAI client
# client = OpenAI()

# Set up tracing processors
# set_trace_processors([OpikTracingProcessor()])
#
# # Patch litellm globally for Opik tracing
# litellm.acompletion = track_completion()(litellm.acompletion)


# =============================================================================
# FALLBACK RESULT CLASSES
# =============================================================================

class FallbackResult:
    """Fallback result for model behavior errors (e.g. null JSON response)."""

    def __init__(self, state: BotState):
        company = (
            state.bot_persona.company_name
            if state.bot_persona
            else "our company"
        )
        fallback_msg = f"I'd be happy to help you learn more about {company}! Could you tell me a bit more about what you're interested in or what challenges you're looking to solve?"
        self.final_output = BotResponse(response=fallback_msg)
        self.last_agent = None
        self.raw_responses = []

    def to_input_list(self) -> List:
        return []


class GuardrailCorrectedResult:
    """Result object for guardrail-corrected responses."""

    def __init__(self, text: str):
        self.final_output = BotResponse(response=text)
        self.last_agent = None
        self.raw_responses = []

    def to_input_list(self) -> List:
        return []


# =============================================================================
# STATE FACTORY FUNCTIONS
# =============================================================================

def create_default_context(
    user_id: str, user_query: str = "", tenant_id: str = ""
) -> UserContext:
    """
    Create a default UserContext for a new user session.

    Args:
        user_id: Unique identifier for the user
        user_query: Initial query from user
        tenant_id: Tenant identifier for multi-tenant setup

    Returns:
        UserContext: Initialized user context
    """
    return UserContext(
        user_id=user_id,
        user_query=user_query,
        tenant_id=tenant_id,
        chat_summary="",
        executive_summary="",
        chat_history=[],
        to_summarise=False,
        retrieved_docs=[],
        contact_details=None,
        follow_trigger=False,
        ask_new_date=False,
        previous_time=None,
        previous_date=None,
        timezone=None,
        region_code=None,
        collected_fields={},
        all_info_collected=False,
        booking_confirmed=False,
        new_booking=False,
    )


def create_bot_state(
    user_id: str,
    user_query: str = "",
    tenant_id: str = "",
    persona: Optional[BotPersona] = None,
) -> BotState:
    """
    Create a complete BotState with context and persona.

    Args:
        user_id: Unique identifier for the user
        user_query: Initial query from user
        tenant_id: Tenant identifier for multi-tenant setup
        persona: Optional custom persona (uses default if None)

    Returns:
        BotState: Fully initialized bot state
    """
    # if persona is None:
    #     persona = create_default_persona()

    context = create_default_context(user_id, user_query, tenant_id)

    return BotState(
        user_context=context,
        bot_persona=persona,
        session_id=None,
        conversation_id=None,
        input_guardrail_decision=None,
        negotiation_state=NegotiationState(
            negotiation_config=persona.negotiation_config
            if persona and persona.negotiation_config
            else None,
        ),
    )


# =============================================================================
# STATE FINALIZATION
# =============================================================================


async def finalize_bot_state(state: BotState, result: Any, user_query: str) -> BotState:
    """
    Consolidates ALL updates from agent result.

    Handles:
    1. Structured output fields (booking info, contact details, etc.)
    2. Execution metadata (query, runner trace, agent names)
    3. Conversation management (history, summary generation)
    4. Probing context updates

    Args:
        state: Current BotState to update
        result: Runner result from agent execution
        user_query: Original user query

    Returns:
        Updated BotState with all changes applied
    """
    logger.info("--- [finalize_bot_state] Starting state finalization ---")

    # 0. Reset per-turn asset sharing flags so they only reflect THIS turn
    state.brochure_flag = False
    state.brochure_details = None
    logger.info("[finalize_bot_state] Reset brochure_flag=False, brochure_details=None for this turn")

    # 1. Extract and Apply Output Data
    output_data = _extract_output_data(result)

    # 2. Update metadata
    state.user_context.user_query = user_query
    state.user_context.agent_result = result.to_input_list()

    # Update last agent name
    latest_agent = _get_last_agent_name(result)
    if latest_agent:
        state.user_context.last_agent = latest_agent
        logger.info(f"Updated last_agent: {latest_agent}")

    # 3. Apply output data to state
    if output_data:
        logger.info(
            f"Applying updates from agent output keys: {list(output_data.keys())}"
        )
        _apply_output_to_state(state, output_data, parent_data=output_data)

    # 3.0 (New) Extract negotiation state from tool calls if main agent dropped it
    try:
        agent_result = state.user_context.agent_result or []
        logger.info(f"[NegExtract] agent_result length: {len(agent_result)}")
        
        # Only process tool calls from the CURRENT turn (after the last user message)
        last_user_idx = -1
        for idx, item in enumerate(agent_result):
            if item.get("role") == "user":
                last_user_idx = idx
        current_turn_items = agent_result[last_user_idx + 1:] if last_user_idx >= 0 else agent_result
        logger.info(f"[NegExtract] Current turn items: {len(current_turn_items)} (from index {last_user_idx + 1})")
        
        # Map call_id to tool name
        tool_calls = {}
        for item in current_turn_items:
            if item.get("type") == "function_call" and item.get("call_id"):
                tool_calls[item.get("call_id")] = item.get("name")
        
        logger.info(f"[NegExtract] Found tool calls: {tool_calls}")

        # Find outputs for negotiation_engine
        for item in current_turn_items:
            if item.get("type") == "function_call_output":
                call_id = item.get("call_id")
                if call_id and call_id in tool_calls and tool_calls[call_id] == "negotiation_engine":
                    logger.info(f"[NegExtract] Processing output for call_id: {call_id}")
                    
                    output_data_raw = item.get("output", "{}")
                    try:
                        if isinstance(output_data_raw, str):
                            if not output_data_raw.strip():
                                logger.warning("[NegExtract] Empty negotiation tool output, skipping")
                                continue
                            output_json = json.loads(output_data_raw)
                        else:
                            output_json = output_data_raw
                        
                        logger.info(f"[NegExtract] Parsed output keys: {output_json.keys()}")
                        
                        # Flatten negotiation_details if present (as per prompt structure)
                        if "negotiation_details" in output_json and isinstance(output_json["negotiation_details"], dict):
                            details = output_json.pop("negotiation_details")
                            output_json.update(details)
                            logger.info("[NegExtract] Flattened negotiation_details for state merge")
    
                        # Merge directly into state using the standard helper
                        _apply_output_to_state(state, {"negotiation_details": output_json})
                        logger.info("[NegExtract] Successfully merged negotiation_details")
                        
                    except Exception as e:
                        logger.error(f"[NegExtract] Failed to parse negotiation tool output: {e}")

    except Exception as e:
        logger.warning(f"Error extracting negotiation tool output: {e}")

    # 3.0b Extract asset sharing details from tool calls if main agent dropped them
    try:
        agent_result = state.user_context.agent_result or []
        
        # Only process tool calls from the CURRENT turn (after the last user message)
        last_user_idx = -1
        for idx, item in enumerate(agent_result):
            if item.get("role") == "user":
                last_user_idx = idx
        current_turn_items = agent_result[last_user_idx + 1:] if last_user_idx >= 0 else agent_result
        logger.info(f"[AssetExtract] Current turn items: {len(current_turn_items)} (from index {last_user_idx + 1})")
        
        # Map call_id to tool name
        tool_calls = {}
        for item in current_turn_items:
            if item.get("type") == "function_call" and item.get("call_id"):
                tool_calls[item.get("call_id")] = item.get("name")
        
        # Find outputs for proceed_with_asset_sharing
        for item in current_turn_items:
            if item.get("type") == "function_call_output":
                call_id = item.get("call_id")
                if call_id and call_id in tool_calls and tool_calls[call_id] == "proceed_with_asset_sharing":
                    logger.info(f"[AssetExtract] Processing output for call_id: {call_id}")
                    
                    output_data_raw = item.get("output")
                    if not output_data_raw or (isinstance(output_data_raw, str) and not output_data_raw.strip()):
                        logger.warning("[AssetExtract] Tool output is empty, skipping")
                        continue
                    try:
                        output_json = None
                        if isinstance(output_data_raw, dict):
                            output_json = output_data_raw
                        elif isinstance(output_data_raw, str):
                            stripped = output_data_raw.strip()
                            # Try standard JSON parse first
                            if stripped.startswith("{"):
                                output_json = json.loads(stripped)
                            else:
                                # Pydantic model __str__ or repr — try to find embedded JSON
                                json_start = stripped.find("{")
                                if json_start != -1:
                                    json_candidate = stripped[json_start:]
                                    try:
                                        output_json = json.loads(json_candidate)
                                    except json.JSONDecodeError:
                                        pass

                                # Still no luck — parse Pydantic repr string with regex
                                if not output_json:
                                    logger.info("[AssetExtract] Attempting regex extraction from Pydantic repr")
                                    output_json = _parse_pydantic_repr_for_asset(stripped)
                        # If output is a Pydantic model object (not serialised)
                        elif hasattr(output_data_raw, "model_dump"):
                            output_json = output_data_raw.model_dump(exclude_unset=True)
                        elif hasattr(output_data_raw, "__dict__"):
                            output_json = {k: v for k, v in output_data_raw.__dict__.items() if v is not None}

                        if not output_json:
                            logger.warning(f"[AssetExtract] Could not parse tool output (type={type(output_data_raw).__name__}): {str(output_data_raw)[:200]}")
                            continue
                        
                        logger.info(f"[AssetExtract] Parsed output keys: {output_json.keys()}")
                        
                        # Extract brochure_details from tool response
                        asset_details = output_json.get("brochure_details")
                        if asset_details and isinstance(asset_details, dict):
                            # Check if any field has a non-null value
                            has_data = any(v is not None for v in asset_details.values())
                            if has_data:
                                _apply_output_to_state(state, {"brochure_details": asset_details})
                                # logger.info(f"[AssetExtract] Successfully merged brochure_details: {asset_details}")
                                
                                # Set brochure flag and details on the state
                                state.brochure_flag = True
                                state.brochure_details = asset_details
                                # logger.info(f"[AssetExtract] Set brochure_flag=True, brochure_details={asset_details}")
                            else:
                                logger.info("[AssetExtract] brochure_details has all null values, skipping")
                        
                        # Also use the tool's response text if main agent response is empty
                        tool_response = output_json.get("response")
                        if tool_response and (not state.response or state.response.strip() == ""):
                            state.response = tool_response
                            # logger.info(f"[AssetExtract] Using tool response as main response: {tool_response[:100]}")
                        
                    except Exception as e:
                        logger.error(f"[AssetExtract] Failed to parse asset sharing tool output: {e}")

    except Exception as e:
        logger.warning(f"Error extracting asset sharing tool output: {e}")

    # 3.1 Update negotiation state based on product selection and probing
    logger.info("[finalize_bot_state] Calling _update_negotiation_dynamic_state...")
    _update_negotiation_dynamic_state(state)
    logger.info(f"[finalize_bot_state] Negotiation state: current_product={state.negotiation_state.negotiation_session.current_product_id if state.negotiation_state and state.negotiation_state.negotiation_session else 'N/A'}, products_count={len(state.negotiation_state.negotiation_session.negotiated_products) if state.negotiation_state and state.negotiation_state.negotiation_session else 0}")

    # 4. Finalize response text - with fallback for empty/null responses
    response_text = state.response

    # Check if response is empty, None, or a stringified empty response
    is_empty_response = (
        not response_text
        or response_text.strip() == ""
        or response_text.strip().lower() == "none"
        or response_text.startswith("response=")  # Stringified Pydantic model fallback
    )

    if is_empty_response:
        # Generate contextual fallback based on conversation state
        logger.warning(
            "[finalize_bot_state] Empty response detected, generating contextual fallback"
        )

        # Check if we're in a CTA flow
        last_agent = state.user_context.last_agent or ""
        company_name = (
            state.bot_persona.company_name if state.bot_persona else "our company"
        )

        if "cta" in last_agent.lower():
            # In CTA flow - ask for specific details or subscription
            fallback_response = "To help you proceed, could you let me know which product you're interested in? I can provide a subscription link or more details based on your choice!"
        elif state.user_context.collected_fields and any(
            state.user_context.collected_fields.values()
        ):
            # We've collected some info - continue the conversation
            fallback_response = f"Thanks for your patience! Is there anything specific about {company_name}'s solutions you'd like to know more about?"
        else:
            # General fallback
            fallback_response = f"I'd be happy to help you learn more about {company_name}! Could you tell me a bit more about what you're interested in or what challenges you're looking to solve?"

        state.response = fallback_response
        logger.info(f"Using fallback response: {fallback_response}")
    else:
        logger.info(f"Final response: {state.response[:50]}...")

    state = await _validate_response_formatting(state)
    
    if state.user_context.last_agent:
        logger.info(f"Last agent in this interaction: {state.user_context.last_agent}")
        last_agent = state.user_context.last_agent
    else:
        last_agent = None

    # 5. Update Chat History
    state = _update_chat_history(state, user_query, last_agent)

    logger.info("--- [finalize_bot_state] Completed ---")

    # 8. Update probing context if present
    _update_probing_context(state, result)

    try:
        consumption = get_individual_token_usage(state, result, last_agent)
        state.consumption_info = ConsumptionInfo(**consumption)
        # Clear temporary storage
        state.additional_raw_responses = []
    except Exception as e:
        logger.error(f"Error getting consumption info: {e}")
        state.consumption_info = ConsumptionInfo()
        
    # DEBUG: Log final negotiation state being returned
    if state.negotiation_state and state.negotiation_state.negotiation_session:
        ns = state.negotiation_state.negotiation_session
        # logger.info(f"[finalize_bot_state] FINAL negotiation_session: current_product_id={ns.current_product_id}, current_product_name={ns.current_product_name}")
        for np_item in ns.negotiated_products:
            logger.info(f"[finalize_bot_state]   Product: {np_item.product_id} ({np_item.product_name}), base_price={np_item.active_base_price}, max_discount={np_item.max_discount_percent}%, current_discount={np_item.current_discount_percent}%, attempts={np_item.negotiation_attempts}")

    _update_human_escalation_context(state, result)

    return state


def _parse_pydantic_repr_for_asset(text: str) -> Optional[Dict[str, Any]]:
    """
    Extract brochure_details and response from a Pydantic model repr string.

    When an agent-as-tool returns a BotResponse, the SDK may serialize it
    via str()/repr() producing:  ``response='...' brochure_details=AssetSharedDetails(asset_id='...', ...)``

    Returns a dict with 'response' and 'brochure_details' keys if found, else None.
    """
    import re as _re

    result: Dict[str, Any] = {}

    # Extract response field  — handles response='...' with nested quotes
    resp_match = _re.search(r"""\bresponse=(['"])(.*?)\1""", text, _re.DOTALL)
    if resp_match:
        result["response"] = resp_match.group(2)

    # Extract brochure_details=AssetSharedDetails(asset_id='...', asset_name='...', asset_path='...')
    bd_match = _re.search(
        r"brochure_details=AssetSharedDetails\(([^)]*)\)", text
    )
    if bd_match:
        inner = bd_match.group(1)
        details: Dict[str, Optional[str]] = {}
        for field in ("asset_id", "asset_name", "asset_path"):
            fm = _re.search(rf"""{field}=(['"])(.*?)\1""", inner)
            if fm:
                details[field] = fm.group(2)
            else:
                # Check for None literal
                nm = _re.search(rf"{field}=None", inner)
                details[field] = None if nm else None
        result["brochure_details"] = details

    if result:
        # logger.info(f"[AssetExtract] Regex extracted: response={'yes' if 'response' in result else 'no'}, brochure_details={'yes' if 'brochure_details' in result else 'no'}")
        return result

    return None


def _extract_output_data(result: Any) -> Dict[str, Any]:
    """Extract output data from runner result."""
    output_data = {}
    if hasattr(result.final_output, "model_dump"):
        output_data = result.final_output.model_dump(exclude_unset=True)
    elif hasattr(result.final_output, "__dict__"):
        output_data = {
            k: v for k, v in result.final_output.__dict__.items() if v is not None
        }
    return output_data


def _get_last_agent_name(result: Any) -> Optional[str]:
    """Get the name of the last agent from result.
    
    Ensures enum members are converted to their string values
    so that stored names like 'sales_agent' match the prompt references.
    """
    if hasattr(result, "last_agent") and hasattr(result.last_agent, "name"):
        name = result.last_agent.name
        # If name is an Enum member, extract its .value string
        if hasattr(name, "value"):
            return name.value
        return str(name)
    return None


def _apply_output_to_state(
    state: BotState, data: Dict[str, Any], depth: int = 0, parent_data: Optional[Dict[str, Any]] = None
) -> None:
    """
    Recursively apply output data to state.

    Args:
        state: BotState to update
        data: Dictionary of output data
        depth: Current recursion depth (for logging)
    """
    for k, v in data.items():
        if v is None:
            continue

        updated = False
        indent = "  " * depth
        
        # DEBUG: Special logging for negotiation data
        if k == "negotiation_details":
            logger.info(f"{indent}[DEBUG] Received negotiation_details with keys: {list(v.keys()) if isinstance(v, dict) else 'not a dict'}")

        # Special case: negotiation_details -> merge into negotiation_state via NegotiationEngine
        if k == "negotiation_details" and isinstance(v, dict):
            logger.info(f"{indent}Merging negotiation_details into negotiation_state via NegotiationEngine")
            
            engine = NegotiationEngine(state)
            engine.update_negotiation_state(v)
            
            # Log merged state
            if state.negotiation_state.negotiation_session:
                ns = state.negotiation_state.negotiation_session
                logger.info(f"{indent}After merge - current_product_id={ns.current_product_id}, current_product_name={ns.current_product_name}, products_count={len(ns.negotiated_products)}")
            
            continue  # Skip other processing for this field

        # Special case: asset_shared_details OR brochure_details → set brochure_flag + brochure_details on BotState
        # Only auto-set brochure_flag=True if the LLM hasn't explicitly provided brochure_flag in the same output
        if k in ("asset_shared_details", "brochure_details") and isinstance(v, dict):
            has_data = any(val is not None for val in v.values())
            root_data = parent_data or data
            llm_explicitly_set_flag = "brochure_flag" in root_data
            if has_data:
                state.brochure_details = v
                if not llm_explicitly_set_flag:
                    state.brochure_flag = True
                    # logger.info(f"{indent}Synced brochure_flag=True from {k}: {v}")
                else:
                    logger.info(f"{indent}Skipped auto-setting brochure_flag (LLM explicitly set brochure_flag={root_data.get('brochure_flag')})")


        # Update state-level attributes
        if hasattr(state, k):
            setattr(state, k, v)
            updated = True
            logger.info(f"{indent}Updated state field: {k}")

        # Update user_context attributes
        if hasattr(state.user_context, k):
            if k == "collected_fields" and isinstance(v, dict):
                existing = state.user_context.collected_fields or {}
                state.user_context.collected_fields = {**existing, **v}
                logger.info(f"{indent}Merged collected_fields")
            else:
                setattr(state.user_context, k, v)
                logger.info(f"{indent}Updated user_context field: {k}")
            updated = True

        # Recursively handle nested dictionaries
        if isinstance(v, dict):
            _apply_output_to_state(state, v, depth + 1, parent_data=parent_data)


@track
async def _validate_response_formatting(state: BotState) -> BotState:
    """
    Validate the response via the RESPONSE_FORMATTER agent.

    Runs spam classification on state.response. If flagged as spam,
    replaces state.response with the regenerated version.
    Wrapped in try/except so a failure never blocks the pipeline.

    Args:
        state: Current BotState with response to validate

    Returns:
        BotState with possibly updated response
    """
    # Skip if there is no response to validate
    if not state.response or state.response.strip() == "":
        logger.info("[RESPONSE_FORMATTER] No response to validate, skipping")
        return state

    try:
        from emailbot.emailagents.factory import get_factory
        from emailbot.core.models import ResponseFormatterOutput

        logger.info("[RESPONSE_FORMATTER] Starting spam validation...")
        logger.info(f"[RESPONSE_FORMATTER] Response length: {len(state.response)}")

        # Create the response formatter agent
        factory = get_factory()
        formatter_agent = factory.get_response_formatter_agent()

        # Build the input — pass the response body to validate
        formatter_input = [
            {
                "role": "user",
                "content": state.response,
            }
        ]

        # Run the agent
        context = RunContextWrapper(state)
        formatter_result = await Runner.run(
            starting_agent=formatter_agent,
            input=formatter_input,
            context=context.context,
        )

        # Parse output
        output = formatter_result.final_output
        if output and isinstance(output, ResponseFormatterOutput):
            if output.is_spam:
                logger.warning(
                    f"[RESPONSE_FORMATTER] Response flagged as SPAM. "
                    f"Reasoning: {output.reasoning}"
                )
                logger.info(
                    f"[RESPONSE_FORMATTER] Original response (first 200): "
                    f"{state.response[:200]}..."
                )
                state.response = output.final_response
                logger.info(
                    f"[RESPONSE_FORMATTER] Rewritten response (first 200): "
                    f"{state.response[:200]}..."
                )
            else:
                logger.info(
                    "[RESPONSE_FORMATTER] Response passed spam check — not spam"
                )
        else:
            logger.warning(
                f"[RESPONSE_FORMATTER] Unexpected output type: {type(output)}, "
                f"skipping validation"
            )

    except Exception as e:
        logger.error(
            f"[RESPONSE_FORMATTER] Error during spam validation: {e}",
            exc_info=True,
        )
        logger.info(
            "[RESPONSE_FORMATTER] Falling through with original response"
        )

    return state
    
    
def _update_chat_history(state: BotState, user_query: str, last_agent: str) -> BotState:
    """Update chat history with new messages."""
    new_history = list(state.user_context.chat_history)
    new_history.append({"role": "user", "content": user_query})
    new_history.append({"role": "assistant", "content": state.response})
    new_history.append({"role": "Last Agent", "content": last_agent})

    if len(new_history) > MAX_HISTORY:
        new_history = new_history[-MAX_HISTORY:]
        logger.info(f"Trimmed chat history to last {MAX_HISTORY} messages")

    state.user_context.chat_history = new_history
    logger.info(f"Updated chat history, total messages: {len(new_history)}")

    return state


def _update_probing_context(state: BotState, result: Any) -> None:
    """
    Update probing context if probing details are present.
    Captures product_id from probing for later use.
    """
    try:
        if (
            hasattr(result.final_output, "probing_details")
            and result.final_output.probing_details
        ):
            state.probing_context, state.objection_state = ProbingEngineState(
                state
            ).update_probing_context(result.final_output.probing_details)
            # probing_details is on user_context, not directly on BotState
            state.user_context.probing_details = getattr(
                result.final_output, "probing_details", None
            )
            # logger.info(f"Updated probing context: {state.probing_context}")
            # logger.debug(f"Probing final output: {result.final_output}")

    except Exception as e:
        logger.error(f"Error updating probing context: {e}")

def _update_human_escalation_context(state: BotState, result: Any) -> None:
    """
    Update human escalation context if human escalation details are present.
    Captures product_id from probing for later use.
    """
    try:
        if (
            hasattr(result.final_output, "human_details")
            and result.final_output.human_details
        ):
            logger.info("Human details found")
            human_details = result.final_output.human_details
            logger.info(f"Human details: {human_details}")
            state.user_context.human_requested = human_details.ready_for_handoff
            state.user_context.human_details = human_details
            
    except Exception as e:
        logger.error(f"Error updating human escalation context: {e}")


def _update_negotiation_dynamic_state(state: BotState, user_query: str = "") -> None:
    """
    Update negotiation state based on detected products and collected fields.
    Uses NegotiationEngine for per-product list management.
    """
    try:
        if not state.negotiation_state:
            logger.warning("No negotiation_state to update")
            return
        
        logger.info("[NegotiationUpdate] Starting negotiation dynamic state update...")
        
        engine = NegotiationEngine(state)
        session = engine._ensure_session("DynamicUpdate")
        
        current_product_id = session.current_product_id
        logger.info(f"[NegotiationUpdate] Existing state - current_product_id: {current_product_id}")
        
        # Update from probing context if product was detected
        if state.probing_context and state.probing_context.detected_product_id:
            product_id = state.probing_context.detected_product_id
            logger.info(f"[NegotiationUpdate] Detected product from probing: {product_id}")
            
            if state.bot_persona and hasattr(state.bot_persona, "company_products"):
                products = state.bot_persona.company_products or []
                for product in products:
                    if hasattr(product, 'id') and product.id == product_id:
                        # logger.info(f"[NegotiationUpdate] Found product: {product.name}")
                        engine._apply_product_to_state(product, source="ProbingContext")
                        break
        
        # Update from collected fields if product info exists there
        if state.user_context.collected_fields:
            collected = state.user_context.collected_fields
            
            if "products" in collected and collected["products"]:
                collected_products = collected["products"]
                if isinstance(collected_products, list):
                    if state.bot_persona and hasattr(state.bot_persona, "company_products"):
                        for prod_name in collected_products:
                            for p in (state.bot_persona.company_products or []):
                                if p.name.strip().lower() == prod_name.strip().lower():
                                    engine._apply_product_to_state(p, source="CollectedFields")
                                    break
            
            if "budget" in collected and collected["budget"]:
                try:
                    budget = float(collected["budget"])
                    # Set budget on current product if one is active
                    if session.current_product_id:
                        np_item = engine._find_negotiated_product(session.current_product_id)
                        if np_item:
                            np_item.user_budget_constraint = budget
                            logger.info(f"[NegotiationUpdate] Set budget constraint: {budget}")
                except (ValueError, TypeError):
                    pass
        
        logger.info(f"[NegotiationUpdate] Final state - products_count={len(session.negotiated_products)}, current_product={session.current_product_id}")
        logger.info("[NegotiationUpdate] Negotiation dynamic state updated successfully")
        
    except Exception as e:
        logger.error(f"Error updating negotiation dynamic state: {e}", exc_info=True)
# =============================================================================
# MAIN API ENTRY POINT
# =============================================================================


@track(name="email-subscription-bot")
async def run_emailbot_api(state: BotState) -> BotState:
    """
    Main API entry point for running the chatbot with BotState.

    This function:
    1. Initializes session and cache
    2. Loads chat history
    3. Runs the agent pipeline
    4. Finalizes state with response
    5. Saves updated state

    Args:
        state: BotState containing user context and agent configuration

    Returns:
        Updated BotState with response and updated context

    Raises:
        AgentExecutionError: If agent execution fails
        GuardrailError: If guardrail validation fails
    """
    user_id = state.user_context.user_id
    unfiltered_user_query = state.user_context.user_query
    user_query = clean_user_query(unfiltered_user_query)
    state.user_context.user_query = user_query

    # Assign message_id for this turn — generate if the incoming state didn't carry one
    if not state.user_context.message_id:
        state.user_context.message_id = str(uuid.uuid4())
    message_id = state.user_context.message_id

    try:
        opik_context.update_current_trace(thread_id=user_id)
    except Exception as e:
        logger.warning(f"could not set thread_id in opik: {e}")

    logger.info("=" * 100)
    logger.info("[run_emailbot_api] Starting chatbot execution")
    # Reset human escalation flag for the new turn
    if state.user_context.human_requested:
        logger.info(f"[run_chatbot_api] Resetting human_requested flag for user {user_id}")
        state.user_context.human_requested = False
        state.user_context.escalation_reason = None

    logger.info(f"message_id={message_id}")
    logger.info(f"User ID: {user_id}")
    logger.info(f"Query: {user_query}")
    logger.info(f"Tenant ID: {state.user_context.tenant_id}")
    logger.info("=" * 100)

    # Load chat history from state.
    # Normalise any HTML-div assistant messages back to Markdown so prompts
    # always receive clean Markdown context regardless of client storage format.
    for msg in state.user_context.chat_history:
        if msg.get("role") == "assistant" and msg.get("content"):
            msg["content"] = html_div_to_markdown(msg["content"])
    chat_history = state.user_context.chat_history

    # Initialize or retrieve session cache,The SDK Auto Manage (Session, Cache, History)
    current_state = await _initialize_session(state, user_id, chat_history)

    # Run semantic cache retrieval
    cached_pairs = _retrieve_cached_pairs(user_id, user_query)
    if cached_pairs:
        current_state.user_context.cache_pairs = cached_pairs

    logger.info(f"Loaded chat history: {len(chat_history)} messages")
    logger.info(
        f"Current collected fields: {current_state.user_context.collected_fields}"
    )

    # Build agent input
    # Pre-detect product to ensure negotiation state is primed for the prompt
    engine = NegotiationEngine(current_state)
    engine.pre_detect_product(user_query)
    
    agent_input = _build_agent_input(current_state, user_query)

    logger.info("************ Starting Runner ***********************")
    # logger.info(f"Input State: {current_state}")
    logger.info("****************************************************")

    # Execute agent
    result = await _execute_agent(current_state, agent_input)

    # Update negotiation state from probing/product detection immediately after agent execution
    logger.info("Updating negotiation state from probing/product detection...")
    _update_negotiation_dynamic_state(current_state)

    # Finalize state and updates
    current_state = await finalize_bot_state(current_state, result, user_query)
    response_text = current_state.response

    # Save state to database
    logger.info("Saving final state to database...")
    # logger.info(f"Final state : {current_state}")
    # save_state(user_id, current_state)

    logger.info("=" * 100)
    logger.info("[run_chatbot_api] Execution completed successfully")
    logger.info(f"Response: {response_text[:100]}...")
    logger.info(
        f"Updated collected fields: {current_state.user_context.collected_fields}"
    )
    logger.info("=" * 100)

    # Save messages to semantic cache
    logger.info("Saving messages to history...")
    update_session(user_id, user_query, result, current_state)
    logger.info("saved to semantic cache")

    # Log prompt cache statistics
    cache_stats = cache_monitor.get_stats()
    if cache_stats["total_requests"] > 0:
        logger.info(
            f"[PROMPT_CACHE] Stats: "
            f"requests={cache_stats['total_requests']} | "
            f"cached_tokens={cache_stats['total_cached_tokens']} | "
            f"hit_rate={cache_stats['overall_cache_hit_rate_pct']}% | "
            f"savings={cache_stats['estimated_input_cost_savings_pct']}%"
        )

    # Convert Markdown response to legacy HTML <div> format for downstream consumers.
    # Applied after save_state and chat-history update so internal storage stays in Markdown.
    current_state.response = markdown_to_html_div(current_state.response)
    logger.info("[run_emailbot_api] Response converted to HTML div format")

    return current_state


async def _initialize_session(
    state: BotState, user_id: str, chat_history: List[Dict[str, str]]
) -> BotState:
    """
    Initialize or retrieve session from cache.

    Args:
        state: Current BotState
        user_id: User identifier
        chat_history: Existing chat history

    Returns:
        Updated BotState with session initialized
    """
    session = get_session(user_id)

    if session:
        logger.info("cache found:")
        logger.info(session.get("messages", []))
        logger.info("Loaded chat history from CACHE")
    else:
        init_session(user_id)
        # Pair up history for semantic cache
        for i in range(0, len(chat_history), 2):
            if i + 1 < len(chat_history):
                user_msg = chat_history[i]
                assistant_msg = chat_history[i + 1]
                if user_msg["role"] == "user" and assistant_msg["role"] == "assistant":
                    update_session(
                        user_id,
                        user_msg["content"],
                        assistant_msg["content"],
                        state=state,
                    )
        logger.info("Loaded chat history from STATE and initialized cache")

    # Create updated state using Pydantic's model_copy
    return state.model_copy(
        update={
            "user_context": state.user_context.model_copy(
                update={"chat_history": chat_history}
            )
        }
    )


def _retrieve_cached_pairs(user_id: str, user_query: str) -> Optional[List[Dict]]:
    """
    Retrieve relevant cached conversation pairs.

    Args:
        user_id: User identifier
        user_query: Current user query

    Returns:
        List of cached pairs or None
    """
    logger.info("Running cache retrieval...")

    cached_pairs = retrieve_from_cache(user_id=user_id, user_query=user_query)

    if cached_pairs:
        logger.info(f"Retrieved {len(cached_pairs)} relevant cached sessions")
        for idx, item in enumerate(cached_pairs, 1):
            logger.info(
                f"[SEMANTIC CACHE MATCH {idx}] "
                f"Score={item['score']:.4f} | "
                f"User={item['user']} | "
                f"Assistant={item['assistant']}"
            )
        logger.info(f"Relevant Data Retrieved from Cache: {cached_pairs}")
        return cached_pairs
    else:
        logger.info("No relevant semantic cache matches found")
        return None


def _build_agent_input(state: BotState, user_query: str) -> List[Dict[str, str]]:
    """
    Build agent input from state and query.

    Args:
        state: Current BotState
        user_query: Current user query

    Returns:
        List of input items for agent
    """
    if state.user_context.agent_result:
        return state.user_context.agent_result + [
            {"content": user_query, "role": "user"}
        ]
    return [{"content": user_query, "role": "user"}]


async def _execute_agent(state: BotState, agent_input: List[Dict[str, str]]) -> Any:
    """
    Execute the agent with the given input.

    Args:
        state: Current BotState
        agent_input: Input for the agent

    Returns:
        Runner result

    Raises:
        AgentExecutionError: If agent execution fails
    """
    logger.info(f"agent input: {agent_input}")

    try:
        context = RunContextWrapper(state)

        # Pass tenant_id so RouterModel uses it as prompt_cache_key
        tenant_id = state.user_context.tenant_id or None

        run_config = RunConfig()

        result = await asyncio.wait_for(
            Runner.run(
                starting_agent=root_agent(tenant_id=tenant_id),
                input=agent_input,
                context=context.context,
                max_turns=25,
                run_config=run_config,
            ),
            timeout=120.0,
        )

        # logger.debug(f"Result from Runner: {result}")

        return result

    except asyncio.TimeoutError:
        logger.error("Agent execution timed out after 120 seconds")
        raise AgentExecutionError(
            agent_name="root_agent",
            reason="Execution timed out after 120 seconds",
        )

    except OutputGuardrailTripwireTriggered as e:
        return _handle_guardrail_tripwire(e)

    except InputGuardrailTripwireTriggered as e:
        return await _handle_input_guardrail_tripwire(e, state, agent_input)

    except Exception as e:
        error_str = str(e)
        logger.error(f"Error running agent: {error_str}")
        logger.exception("Full traceback:")

        # Check if this is a model behavior error with null response
        # In this case, return a fallback response instead of crashing
        if (
            "Invalid JSON" in error_str
            and "response" in error_str
            and "null" in error_str.lower()
        ):
            logger.warning("Model returned null response, using contextual fallback")
            return FallbackResult(state)

        raise AgentExecutionError(
            agent_name="root_agent", reason=str(e), original=e
        ) from e


def _handle_guardrail_tripwire(error: OutputGuardrailTripwireTriggered) -> Any:
    """
    Handle guardrail tripwire trigger by extracting suggested text.

    Args:
        error: OutputGuardrailTripwireTriggered exception

    Returns:
        Result with suggested text or contextual fallback response
    """
    logger.warning(f"Output guardrail tripwire triggered: {error}")

    suggested_text = None

    # The SDK passes OutputGuardrailResult as first arg
    # OutputGuardrailResult has: guardrail, agent, agent_output, output_info
    if error.args:
        guardrail_result = error.args[0]
        logger.info(f"Guardrail result type: {type(guardrail_result)}")

        # If it's a string (just the error message), try to get more info
        if isinstance(guardrail_result, str):
            logger.info(f"Guardrail result is a string: {guardrail_result}")
        else:
            # It's an OutputGuardrailResult object
            logger.info(f"Guardrail result attributes: {dir(guardrail_result)}")

            # Check if it has output_info (SDK OutputGuardrailResult structure)
            if hasattr(guardrail_result, "output_info"):
                output_info = guardrail_result.output_info
                logger.info(f"Output info type: {type(output_info)}")
                logger.info(f"Output info: {output_info}")

                # output_info could be our OutputGuardrail model
                if (
                    hasattr(output_info, "suggested_text")
                    and output_info.suggested_text
                ):
                    suggested_text = output_info.suggested_text
                elif isinstance(output_info, dict) and output_info.get(
                    "suggested_text"
                ):
                    suggested_text = output_info["suggested_text"]

            # Direct suggested_text on result
            if (
                not suggested_text
                and hasattr(guardrail_result, "suggested_text")
                and guardrail_result.suggested_text
            ):
                suggested_text = guardrail_result.suggested_text

            # Result might be a dict
            if not suggested_text and isinstance(guardrail_result, dict):
                suggested_text = guardrail_result.get(
                    "suggested_text"
                ) or guardrail_result.get("output_info", {}).get("suggested_text")

    # Generate contextual fallback if no suggested text found
    if not suggested_text:
        logger.warning("No suggested text found, generating contextual fallback")
        suggested_text = "I'd be happy to help you! Could you please tell me more about what you're looking for? I can assist with information about our products, booking demos, or answering any questions you might have."

    logger.info(f"Using response text: {suggested_text}")

    logger.info("Proceeding with guardrail-corrected response")
    return GuardrailCorrectedResult(suggested_text)


async def _handle_input_guardrail_tripwire(
    error: InputGuardrailTripwireTriggered,
    state: BotState,
    agent_input: List[Dict[str, str]],
) -> Any:
    """
    Handle input guardrail tripwire by extracting the pre-generated response
    from the guardrail result — no extra agent call needed.

    The guardrail agent now returns a 'response' field with a contextual,
    user-facing deflection message when it flags an attack query.

    Args:
        error: InputGuardrailTripwireTriggered exception
        state: Current BotState for context
        agent_input: Original agent input (unused, kept for signature compat)

    Returns:
        A result-like object whose final_output is a BotResponse
    """
    logger.warning(f"Input guardrail tripwire triggered: {error}")

    # Record the guardrail decision in state for monitoring
    guardrail_response = ""

    # Try reading from state first (set by guardrail via ctx.context)
    input_decision = getattr(state, "input_guardrail_decision", None)

    # Fall back to SDK exception object
    if not input_decision:
        try:
            guardrail_result = error.guardrail_result
            output_info = guardrail_result.output.output_info
            input_decision = output_info
        except Exception:
            pass

    if input_decision:
        logger.info(f"Input guardrail decision: {input_decision}")
        state.input_guardrail_decision = input_decision
        guardrail_response = getattr(input_decision, "response", "") or ""

    # Also try extracting from the SDK exception object directly
    if not guardrail_response:
        try:
            guardrail_result = error.guardrail_result
            output_info = guardrail_result.output.output_info
            if hasattr(output_info, "response"):
                guardrail_response = output_info.response or ""
        except Exception:
            pass

    # Fallback if guardrail somehow didn't produce a response
    if not guardrail_response:
        company_name = (
            state.bot_persona.company_name if state.bot_persona else "our company"
        )
        guardrail_response = (
            f"I'm here to help you with questions about {company_name} "
            f"and our products and services. Could you please rephrase "
            f"your question so I can assist you better?"
        )
        logger.info("[input_guardrail_handler] Using fallback response")

    logger.info(f"[input_guardrail_handler] Returning guardrail response: {guardrail_response[:100]}...")

    class _AgentRef:
        """Minimal stand-in so _get_last_agent_name can read .last_agent.name."""
        def __init__(self, name: str):
            self.name = name

    class InputGuardrailResult:
        def __init__(self, text: str):
            self.final_output = BotResponse(response=text)
            self.last_agent = _AgentRef("input_guardrail_agent")
            self.raw_responses = []

        def to_input_list(self) -> List:
            return []

    return InputGuardrailResult(guardrail_response)