"""
Response Formatter Agent — Spam detection and response regeneration.

This module contains the response formatter agent definition including:
- Dynamic instruction generator
- Agent creator function

The agent validates generated email responses for spam and rewrites
them if flagged, following the same pattern as negotiation/agent.py.
"""

from opik import track
from agents import Agent
from typing import Optional

from emailbot.config import logger

from emailbot.config.constants import AgentName


# =============================================================================
# DYNAMIC INSTRUCTION GENERATOR
# =============================================================================
@track
def dynamic_response_formatter_instructions(context, agent) -> str:
    """
    Generate dynamic instructions for the response formatter agent.

    Validates email responses against spam criteria and regenerates
    if necessary.

    Args:
        context: RunContextWrapper containing BotState
        agent: Agent instance

    Returns:
        Formatted prompt string for spam classification + regeneration
    """
    logger.info("=" * 60)
    logger.info(
        "[dynamic_response_formatter_instructions] Generating response formatter instructions"
    )

    try:
        from emailbot.prompts import get_response_formatter_prompt

        state = context.context
        logger.info(f"User ID: {state.user_context.user_id}")
        logger.info(f"Response to validate length: {len(state.response or '')}")

        prompt = get_response_formatter_prompt(state)
        logger.info(
            f"Generated response formatter prompt (first 200 chars): {prompt[:200]}..."
        )
        logger.info("=" * 60)

        return prompt

    except Exception as e:
        logger.error(f"Error generating response formatter instructions: {e}")
        logger.exception("Full traceback:")
        return "You are a response formatter. Check if the email response is spam and rewrite if needed."


# =============================================================================
# AGENT CREATOR
# =============================================================================
def create_response_formatter_agent(tenant_id: Optional[str] = None) -> Agent:
    """
    Create the response formatter agent for spam validation.

    Capabilities:
    - Spam classification of generated email responses
    - Conditional regeneration of flagged responses
    - Preservation of original content when not spam

    Returns:
        Configured response formatter Agent
    """
    from emailbot.emailagents.config import (
        get_primary_model,
        get_model_settings,
    )
    from emailbot.core.models import ResponseFormatterOutput

    logger.info(f"create_response_formatter_agent - get_primary_model() : {get_primary_model()}")
    logger.info(f"create_response_formatter_agent - get_model_settings() : {get_model_settings()}")

    return Agent(
        name=AgentName.RESPONSE_FORMATTER.value,
        instructions=dynamic_response_formatter_instructions,
        model=get_primary_model(tenant_id=tenant_id),
        model_settings=get_model_settings(),
        output_type=ResponseFormatterOutput,
    )