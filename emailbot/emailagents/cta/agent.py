"""
CTA Agent - Call To Action, including subscriptions.

This module contains the CTA agent definition including:
- Dynamic instruction generator for CTA
- Agent creator function
"""

from opik import track
from agents import Agent
from typing import Optional
from emailbot.config.settings import logger


from emailbot.config.constants import AgentName, AGENT_HANDOFF_DESCRIPTIONS


# =============================================================================
# DYNAMIC INSTRUCTION GENERATOR
# =============================================================================


@track
def dynamic_cta_instructions(context, agent) -> str:
    """
    Generate dynamic instructions for CTA agent.

    Handles:
    - CTA requests (subscription links)
    - New booking requests
    - Rescheduling existing bookings
    - Cancellation requests
    - Lead quality analysis after successful bookings

    Args:
        context: RunContextWrapper containing BotState
        agent: Agent instance

    Returns:
        Formatted prompt string for CTA
    """
    logger.info("=" * 60)
    logger.info("[dynamic_cta_instructions] Generating CTA instructions")

    try:
        from emailbot.prompts import cta_prompt

        state = context.context
        logger.info(f"User ID: {state.user_context.user_id}")
        logger.info(f"Collected fields: {state.user_context.collected_fields}")
        logger.info(f"Booking confirmed: {state.user_context.booking_confirmed}")
        logger.info(f"Booking type: {state.user_context.booking_type}")

        prompt = cta_prompt(state)
        logger.info(f"Generated CTA prompt (first 200 chars): {prompt[:200]}...")
        logger.info("=" * 60)

        return prompt

    except Exception as e:
        logger.error(f"Error generating CTA instructions: {e}")
        logger.exception("Full traceback:")
        return (
            "You are a CTA assistant. Help the user with their request or schedule a product demonstration. "
            "Use available tools for datetime validation and calendly checking."
        )


# =============================================================================
# AGENT CREATOR
# =============================================================================


def create_cta_agent(tenant_id: Optional[str] = None) -> Agent:
    """
    Create the CTA agent with comprehensive support for Call To Action and booking workflows.

    Capabilities:
    - SUBSCRIPTION: Provides subscription links when requested
    - PLAN ACTIVATION: Handles the final step toward subscription
    - LEAD ANALYSIS: Analyzes lead quality after successful CTA conversion

    Tools:
    - get_timezone: Detects user timezone
    - process_booking_datetime: UNIFIED tool that parses datetime expressions, validates
      against business rules, and converts to UTC in a single call
    - check_calendly_availability: Checks Calendly for slot availability
    - lead_analysis_tool: Analyzes lead quality after successful bookings

    Returns:
        Configured CTA Agent
    """
    from emailbot.tools.followup_timezone import get_timezone
    from emailbot.tools.booking_tools import (
        process_booking_datetime,  # Unified datetime processing tool
        check_calendly_availability,
    )
    from emailbot.emailagents.lead_analysis import create_lead_analysis_agent
    from emailbot.emailagents.config import (
        get_primary_model,
        get_model_settings,
        get_output_schema,
    )

    # Create lead analysis as a tool
    lead_analysis_tool = create_lead_analysis_agent(tenant_id=tenant_id).as_tool(
        tool_name="lead_analysis_tool",
        tool_description=(
            "Use this tool when booking is confirmed and booking type is not 'cancel'. "
            "Analyze lead quality based on conversation history and contact details. "
            "Return classification: 'hot' (high urgency, eager), 'warm' (engaged, considering), "
            "or 'cold' (minimal engagement). Consider eagerness, urgency, specific needs, "
            "and engagement level to prioritize follow-up."
        ),
    )

    return Agent(
        name=AgentName.CTA.value,
        handoff_description=AGENT_HANDOFF_DESCRIPTIONS[AgentName.CTA],
        instructions=dynamic_cta_instructions,
        model=get_primary_model(tenant_id=tenant_id),
        model_settings=get_model_settings(),
        tools=[
            get_timezone,
            process_booking_datetime,
            lead_analysis_tool,
            check_calendly_availability,
        ],
        # output_guardrails=get_output_guardrails(), # commented out for now
        output_type=get_output_schema(),
    )
