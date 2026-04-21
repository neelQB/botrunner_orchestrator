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
def dynamic_sales_instructions(context, agent) -> str:
    """
    Generate dynamic instructions for sales agent.

    Args:
        context: RunContextWrapper containing BotState
        agent: Agent instance

    Returns:
        Formatted prompt string for sales conversations
    """
    logger.info("=" * 60)
    logger.info("[dynamic_sales_instructions] Generating sales instructions")

    try:
        from emailbot.prompts import sales_prompt

        state = context.context
        logger.info(f"User ID: {state.user_context.user_id}")

        prompt = sales_prompt(state)
        logger.info(f"Generated sales prompt (first 200 chars): {prompt[:200]}...")
        logger.info("=" * 60)

        return prompt

    except Exception as e:
        logger.error(f"Error generating sales instructions: {e}")
        logger.exception("Full traceback:")
        return "You are a sales assistant. Help the user with product inquiries."


# =============================================================================
# AGENT CREATOR
# =============================================================================


def create_sales_agent(tenant_id: Optional[str] = None) -> Agent:
    """
    Create the sales agent for product inquiries.

    Tools:
    - retrieve_query: RAG query for knowledge base search
    - objection_handle_agent: Handles user objections with re-engagement strategy

    Returns:
        Configured sales Agent
    """
    from emailbot.tools.sales_tools import retrieve_query
    from emailbot.emailagents.config import (
        get_primary_model,
        get_model_settings,
        get_output_schema,
    )
    from emailbot.emailagents.objection_handle import create_objection_handle_agent

    # Instantiate the objection-handle agent and expose it as a tool
    objection_handle_agent = create_objection_handle_agent(tenant_id=tenant_id)

    objection_handle_tool = objection_handle_agent.as_tool(
        tool_name="objection_handle_agent",
        tool_description=(
            "CRITICAL: Call this tool IMMEDIATELY when user expresses ANY objection or rejection. "
            "Examples: 'not interested', 'too expensive', 'no thanks', 'go away', 'maybe later', 'stop', "
            "'don't need this', 'not for me', 'already have', 'waste of time', 'pass', 'no', or ANY form of disinterest/dismissal. "
            "This tool handles objection with re-engagement strategy and returns: (1) Empathetic response, "
            "(2) Updated objection state, (3) Can-show-CTA flag based on probing status. "
            "NEVER respond directly to objections—ALWAYS use this tool first."
        ),
    )

    return Agent(
        name=AgentName.SALES.value,
        handoff_description=(
            "Used for handling user's query when user communicates about products "
            "or company related details. 'ask about your products', 'pricing details', "
            "'features', 'company info', etc."
        ),
        instructions=dynamic_sales_instructions,
        model=get_primary_model(tenant_id=tenant_id),
        model_settings=get_model_settings(),
        tools=[retrieve_query, objection_handle_tool],
        # output_guardrails=get_output_guardrails(),
        output_type=get_output_schema(),
    )
