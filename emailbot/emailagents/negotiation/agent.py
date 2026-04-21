"""
Sales Agent - Product inquiries and lead generation.

This module contains the sales agent definition including:
- Dynamic instruction generator
- Agent creator function

Tools are imported from emailbot.tools.sales_tools (not moved here).
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
def dynamic_negotiation_instructions(context, agent) -> str:
    """
    Generate dynamic instructions for negotiation engine agent.

    Handles pricing negotiation with strategic tactics and business rules.

    Args:
        context: RunContextWrapper containing BotState
        agent: Agent instance

    Returns:
        Formatted prompt string for pricing negotiation
    """
    logger.info("=" * 60)
    logger.info(
        "[dynamic_negotiation_instructions] Generating negotiation engine instructions"
    )

    try:
        from emailbot.prompts.negotiation import get_pricing_negotiation_prompt

        state = context.context
        logger.info(f"User ID: {state.user_context.user_id}")
        logger.info(f"Negotiation context available: {hasattr(state, 'pricing_context')}")

        prompt = get_pricing_negotiation_prompt(state)
        logger.info(
            f"Generated negotiation prompt {prompt}"
        )
        logger.info("=" * 60)

        return prompt

    except Exception as e:
        logger.error(f"Error generating negotiation instructions: {e}")
        logger.exception("Full traceback:")
        return "You are a pricing negotiation specialist. Help negotiate pricing strategically with clients."




# =============================================================================
# AGENT CREATOR
# =============================================================================
def create_negotiation_engine_agent(tenant_id: Optional[str] = None) -> Agent:
    """
    Create the negotiation engine agent for pricing negotiations.

    Capabilities:
    - Strategic pricing negotiation with business rules
    - Discount management with ceiling limits
    - Psychological tactics for client engagement
    - Price locking mechanism
    - Multi-round negotiation support

    Returns:
        Configured negotiation engine Agent
    """
    from emailbot.emailagents.config import (
        get_primary_model,
        get_model_settings,
    )
    from emailbot.core.models import NegotiationAgentResponse

    return Agent(
        name=AgentName.NEGOTIATION_ENGINE.value,
        instructions=dynamic_negotiation_instructions,
        model=get_primary_model(tenant_id=tenant_id),
        model_settings=get_model_settings(),
        output_type=NegotiationAgentResponse,
    )
