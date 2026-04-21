"""
Human Escalation Agent - Escalation to human support.

This module contains the human escalation agent definition including:
- Dynamic instruction generator
- Agent creator function

Tools are imported from emailbot.tools.human_tools (not moved here).
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
def dynamic_human_instructions(context, agent) -> str:
    """
    Generate dynamic instructions for human escalation agent.

    Args:
        context: RunContextWrapper containing BotState
        agent: Agent instance

    Returns:
        Formatted prompt string for human escalation
    """
    logger.info("=" * 60)
    logger.info("[dynamic_human_instructions] Generating human escalation instructions")

    try:
        from emailbot.prompts import human_agent_prompt

        state = context.context
        logger.info(f"User ID: {state.user_context.user_id}")
        logger.info(f"Human requested: {state.user_context.human_requested}")
        logger.info(f"Escalation reason: {state.user_context.escalation_reason}")

        prompt = human_agent_prompt(state)
        logger.info(
            f"Generated human escalation prompt (first 200 chars): {prompt[:200]}..."
        )
        logger.info("=" * 60)

        return prompt

    except Exception as e:
        logger.error(f"Error generating human escalation instructions: {e}")
        logger.exception("Full traceback:")
        return "You are a customer success representative. Help the user connect with a human agent."


# =============================================================================
# AGENT CREATOR
# =============================================================================


def create_human_agent(tenant_id: Optional[str] = None) -> Agent:
    """
    Create the human escalation agent.

    No tools — this agent simply informs the user that a team member
    is busy and will connect with them shortly.

    Returns:
        Configured human Agent
    """
    from emailbot.emailagents.config import (
        get_primary_model,
        get_model_settings,
        get_output_guardrails,
        get_output_schema,
    )

    return Agent(
        name=AgentName.HUMAN.value,
        handoff_description=(
            "Used when user explicitly requests to speak with a human agent, customer support, "
            "or real person. Hand off when user says: "
            "'talk to human', 'connect me with someone', 'I want to speak with your team', "
            "'get me a real person', 'transfer to support', 'I need a manager', "
            "'can I speak with someone', 'I want to talk to a real person', "
            "'is there anyone I can talk to?', or similar explicit requests "
            "for a live conversation with a human team member."
            "for greetings or normal query not escalation"
        ),
        instructions=dynamic_human_instructions,
        model=get_primary_model(tenant_id=tenant_id),
        model_settings=get_model_settings(),
        output_type=get_output_schema(),
    )
