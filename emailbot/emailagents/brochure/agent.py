"""
Asset Sharing (Brochure) Agent - Handles sharing assets with users.

This module contains the asset sharing agent definition including:
- Dynamic instruction generator
- Agent creator function

Follows the same agent-as-tool pattern as negotiation_engine.
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
def dynamic_asset_sharing_instructions(context, agent) -> str:
    """
    Generate dynamic instructions for the asset sharing agent.

    Args:
        context: RunContextWrapper containing BotState
        agent: Agent instance

    Returns:
        Formatted prompt string for asset sharing flow
    """
    logger.info("=" * 60)
    logger.info(
        "[dynamic_asset_sharing_instructions] Generating asset sharing instructions"
    )

    try:
        from emailbot.prompts import asset_sharing_prompt

        state = context.context
        logger.info(f"Bot state type: {type(state)}")

        prompt = asset_sharing_prompt(state)
        logger.info(
            f"Generated asset sharing prompt (first 200 chars): {prompt[:200]}..."
        )
        logger.info("=" * 60)

        return prompt

    except Exception as e:
        logger.error(f"Error generating asset sharing instructions: {e}")
        logger.exception("Full traceback:")
        return "You are an asset sharing assistant. Help users find and access documents, brochures, and files."


# =============================================================================
# AGENT CREATOR
# =============================================================================


def create_asset_sharing_agent(tenant_id: Optional[str] = None) -> Agent:
    """
    Create the asset sharing agent (used as a tool by the main agent).

    Handles sharing brochures, documents, files, and other assets
    with users.

    Returns:
        Configured asset sharing Agent
    """
    from emailbot.emailagents.config import (
        get_primary_model,
        get_model_settings,
        get_output_schema,
    )

    return Agent(
        name=AgentName.ASSET_SHARING.value,
        instructions=dynamic_asset_sharing_instructions,
        model=get_primary_model(tenant_id=tenant_id),
        model_settings=get_model_settings(),
        output_type=get_output_schema(),
    )
