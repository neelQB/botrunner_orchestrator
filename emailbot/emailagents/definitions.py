"""
Agent Definitions - Agent creators and shared configuration.

This module provides re-exports of all agent creator functions from 
submodules and the main agent instructions (root agent).

Agent implementations are located in:
- emailbot.emailagents.sales             → Sales Agent
- emailbot.emailagents.cta               → CTA Agent
- emailbot.emailagents.followup          → Follow-up Agent
- emailbot.emailagents.human_escalation  → Human Escalation Agent
- emailbot.emailagents.lead_analysis     → Lead Analysis Agent

To add a new agent:
1. Create a new submodule in emailbot/emailagents/ (e.g., emailbot/emailagents/my_agent/)
2. Create __init__.py with create_my_agent() function
3. Import and re-export it here in the RE-EXPORTS section
4. Add to factory.py _creators dict

Usage:
    ```python
    from emailbot.emailagents.definitions import create_sales_agent
    
    sales_agent = create_sales_agent()
    ```
"""


from opik import track

from emailbot.config.settings import logger

# =============================================================================
# RE-EXPORTS FROM AGENT SUBMODULES
# =============================================================================

from emailbot.emailagents.sales import create_sales_agent, dynamic_sales_instructions
from emailbot.emailagents.cta import create_cta_agent, dynamic_cta_instructions
from emailbot.emailagents.followup import create_followup_agent, dynamic_followup_instructions
from emailbot.emailagents.human_escalation import create_human_agent, dynamic_human_instructions
from emailbot.emailagents.lead_analysis import create_lead_analysis_agent
from emailbot.emailagents.negotiation import create_negotiation_engine_agent, dynamic_negotiation_instructions
from emailbot.emailagents.brochure import create_asset_sharing_agent, dynamic_asset_sharing_instructions
from emailbot.emailagents.objection_handle import create_objection_handle_agent, dynamic_objection_handle_instructions
from emailbot.emailagents.response_formatter import create_response_formatter_agent, dynamic_response_formatter_instructions

# =============================================================================
# MAIN AGENT INSTRUCTIONS (no subfolder for root/main agent)
# =============================================================================


@track
def dynamic_main_instructions(context, agent) -> str:
    """
    Generate dynamic instructions for main agent.

    Args:
        context: RunContextWrapper containing BotState
        agent: Agent instance

    Returns:
        Formatted prompt string for main conversation
    """
    logger.info("=" * 60)
    logger.info("[dynamic_main_instructions] Generating main agent instructions")

    try:
        from emailbot.prompts import main_prompt

        state = context.context
        logger.info(f"User ID: {state.user_context.user_id}")
        logger.info(f"Company: {state.bot_persona.company_name}")
        logger.info(f"Agent name: {state.bot_persona.name}")
        logger.info(
            f"Chat history length: {len(state.user_context.chat_history or [])}"
        )
        logger.info(f"Last agent: {state.user_context.last_agent}")

        prompt = main_prompt(state)
        logger.info(f"Generated main prompt (first 200 chars): {prompt[:200]}...")
        logger.info("=" * 60)

        return prompt

    except Exception as e:
        logger.error(f"Error generating main instructions: {e}")
        logger.exception("Full traceback:")
        return f"You are {state.bot_persona.name}, an AI assistant for {state.bot_persona.company_name}."
