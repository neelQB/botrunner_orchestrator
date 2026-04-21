"""
Objection Handle Agent - Re-engagement for user objections.

This module contains the objection handle agent definition including:
- Dynamic instruction generator
- Agent creator function
"""

from opik import track
from agents import Agent
from typing import Optional

from emailbot.config.settings import logger
from emailbot.config.constants import AgentName


# =============================================================================
# DYNAMIC INSTRUCTION GENERATOR
# =============================================================================


@track
def dynamic_objection_handle_instructions(context, agent) -> str:
    """
    Generate dynamic instructions for objection handle agent.

    Args:
        context: RunContextWrapper containing BotState
        agent: Agent instance

    Returns:
        Formatted prompt string for objection handling
    """
    logger.info("=" * 60)
    logger.info(
        "[dynamic_objection_handle_instructions] Generating objection handle instructions"
    )

    try:
        from emailbot.prompts import objection_handle_prompt

        state = context.context
        logger.info(f"Bot state type: {type(state)}")

        prompt = objection_handle_prompt(state)
        logger.info(
            f"Generated objection handle prompt (first 200 chars): {prompt[:200]}..."
        )
        logger.info("=" * 60)

        return prompt

    except Exception as e:
        logger.error(f"Error generating objection handle instructions: {e}")
        logger.exception("Full traceback:")
        return "You are an objection handle assistant. Help handle objections from the user."


# =============================================================================
# AGENT CREATOR
# =============================================================================


def create_objection_handle_agent(tenant_id: Optional[str] = None) -> Agent:
    """
    Create the objection handling agent.

    Tools:
    - retrieve_query: RAG query for knowledge base search to enrich objection responses

    Returns:
        Configured objection handle Agent
    """
    from emailbot.tools.sales_tools import retrieve_query
    from emailbot.emailagents.config import (
        get_primary_model,
        get_model_settings,
        get_output_schema,
    )

    return Agent(
        name=AgentName.OBJECTION_HANDLE.value,
        instructions=dynamic_objection_handle_instructions,
        model=get_primary_model(tenant_id=tenant_id),
        model_settings=get_model_settings(),
        tools=[retrieve_query],
        output_type=get_output_schema(),
    )

