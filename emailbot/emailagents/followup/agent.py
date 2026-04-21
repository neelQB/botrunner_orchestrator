"""
Follow-up Agent - Post-demo engagement and scheduling.

This module contains the follow-up agent definition including:
- Dynamic instruction generator
- Agent creator function

Tools are imported from emailbot.tools.followup_timezone (not moved here).
"""

from opik import track
from agents import Agent
from typing import Optional

from emailbot.config.constants import AgentName


# =============================================================================
# DYNAMIC INSTRUCTION GENERATOR
# =============================================================================


@track
def dynamic_followup_instructions(context, agent) -> str:
    """
    Generate dynamic instructions for followup agent.

    Args:
        context: RunContextWrapper containing BotState
        agent: Agent instance

    Returns:
        Formatted prompt string for followup handling
    """
    logger.info("=" * 60)
    logger.info("[dynamic_followup_instructions] Generating followup instructions")

    try:
        from emailbot.prompts import followup_prompt

        state = context.context
        logger.info(f"User ID: {state.user_context.user_id}")
        logger.info(f"Follow trigger: {state.user_context.follow_trigger}")

        prompt = followup_prompt(state)
        logger.info(f"Generated followup prompt (first 200 chars): {prompt[:200]}...")
        logger.info("=" * 60)

        return prompt

    except Exception as e:
        logger.error(f"Error generating followup instructions: {e}")
        logger.exception("Full traceback:")
        return "You are a followup assistant. Help schedule future interactions with the user."


# =============================================================================
# AGENT CREATOR
# =============================================================================


def create_followup_agent(tenant_id: Optional[str] = None) -> Agent:
    """
    Create the followup agent for scheduling future interactions.

    Tools:
    - get_timezone: Detects user timezone
    - process_followup_datetime: Unified tool for parsing, validating, and converting follow-up times

    Returns:
        Configured followup Agent
    """
    from emailbot.tools.followup_timezone import get_timezone, process_followup_datetime
    from emailbot.emailagents.config import (
        get_primary_model,
        get_model_settings,
        get_output_schema,
    )

    return Agent(
        name=AgentName.FOLLOWUP.value,
        handoff_description=(
            "Used for handling user's query when user wants followup later OR is "
            "responding to a follow-up scheduling question. Hand off when user says "
            "'ping me in 5 min', 'remind me later', 'contact me tomorrow', "
            "or provides a time/date for a follow-up."
        ),
        instructions=dynamic_followup_instructions,
        model=get_primary_model(tenant_id=tenant_id),
        model_settings=get_model_settings(),
        tools=[get_timezone, process_followup_datetime],
        # output_guardrails=get_output_guardrails(), # commented out for now
        output_type=get_output_schema(),
    )
