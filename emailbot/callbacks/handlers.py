"""
Callback Handlers - Handoff callback implementations.

This module contains all callback handlers that are executed when
an agent hands off control to another agent. Callbacks are used to:
- Update state before handoff
- Log handoff events
- Perform cleanup or initialization

Usage:
    from emailagents import handoff
    from emailbot.callbacks.handlers import on_sales_handoff
    
    handoff(agent=sales_agent, on_handoff=on_sales_handoff)
"""

from datetime import datetime, timezone
from typing import Any

from agents import RunContextWrapper


from emailbot.config.settings import logger
from opik import track

from emailbot.core.models import BotState, HandoffArgs
from emailbot.config.constants import AgentName


# =============================================================================
# HANDOFF CALLBACK HANDLERS
# =============================================================================


@track
def on_sales_handoff(ctx: RunContextWrapper[BotState], Args: HandoffArgs) -> BotState:
    """
    Callback function when handing off to sales agent.

    Updates:
    - Sets new_booking flag to True

    Args:
        ctx: RunContextWrapper containing BotState
        Args: HandoffArgs containing handoff arguments

    Returns:
        Updated BotState
    """
    logger.info("*" * 60)
    logger.info("[on_sales_handoff] Sales Handoff Initiated")

    try:
        state = ctx.context
        state.user_context.user_language = Args.user_language
        state.user_context.user_script = Args.user_script
        logger.info(f"User ID: {state.user_context.user_id}")

        # Update state
        state.user_context.new_booking = True

        logger.info("[on_sales_handoff] State updated")
        logger.info("*" * 60)

        return state

    except Exception as e:
        logger.error(f"Error in sales handoff: {e}")
        logger.exception("Full traceback:")
        return ctx.context


@track
def on_cta_handoff(ctx: RunContextWrapper[BotState], Args: HandoffArgs) -> BotState:
    """
    Callback function when handing off to CTA agent.

    Updates:
    - Sets new_booking flag to True

    Args:
        ctx: RunContextWrapper containing BotState
        Args: HandoffArgs containing handoff arguments

    Returns:
        Updated BotState
    """
    logger.info("*" * 60)
    logger.info("[on_cta_handoff] CTA Handoff Initiated")

    try:
        state = ctx.context
        state.user_context.user_language = Args.user_language
        state.user_context.user_script = Args.user_script
        logger.info(f"User ID: {state.user_context.user_id}")
        logger.info(f"Current collected fields: {state.user_context.collected_fields}")
        logger.info(f"Booking status: {state.user_context.booking_confirmed}")

        # Update state
        state.user_context.new_booking = True

        logger.info("[on_cta_handoff] State updated with new_booking=True")
        logger.info("*" * 60)

        return state

    except Exception as e:
        logger.error(f"Error in CTA handoff: {e}")
        logger.exception("Full traceback:")
        return ctx.context


@track
def on_followup_handoff(ctx: RunContextWrapper[BotState], Args: HandoffArgs) -> BotState:
    """
    Callback function when handing off to followup agent.

    Updates:
    - Sets follow_trigger flag to True

    Args:
        ctx: RunContextWrapper containing BotState
        Args: HandoffArgs containing handoff arguments

    Returns:
        Updated BotState
    """
    logger.info("*" * 60)
    logger.info("[on_followup_handoff] Followup Handoff Initiated")

    try:
        state = ctx.context
        state.user_context.user_language = Args.user_language
        state.user_context.user_script = Args.user_script
        logger.info(f"User ID: {state.user_context.user_id}")
        logger.info(f"Previous date: {state.user_context.previous_date}")
        logger.info(f"Previous time: {state.user_context.previous_time}")

        # Update state
        state.user_context.follow_trigger = True

        logger.info("[on_followup_handoff] State updated with follow_trigger=True")
        logger.info("*" * 60)

        return state

    except Exception as e:
        logger.error(f"Error in followup handoff: {e}")
        logger.exception("Full traceback:")
        return ctx.context


@track
def on_human_handoff(ctx: RunContextWrapper[BotState], Args: HandoffArgs) -> BotState:
    """
    Callback function when handing off to human agent.

    Updates:
    - Sets human_requested flag to True
    - Records escalation timestamp

    Args:
        ctx: RunContextWrapper containing BotState
        Args: HandoffArgs containing handoff arguments
    Returns:
        Updated BotState
    """
    logger.info("*" * 60)
    logger.info("[on_human_handoff] Human Escalation Handoff Initiated")

    try:
        state = ctx.context
        state.user_context.user_language = Args.user_language
        state.user_context.user_script = Args.user_script
        logger.info(f"User ID: {state.user_context.user_id}")
        logger.info(f"Current escalation status: {state.user_context.human_requested}")

        # Get current UTC time for escalation timestamp
        utc_time = datetime.now(timezone.utc).isoformat()

        # Update state
        state.user_context.human_requested = True
        state.user_context.escalation_timestamp = utc_time
        state.user_context.last_agent = AgentName.HUMAN.value

        logger.info("[on_human_handoff] State updated with human_requested=True")
        logger.info(f"Escalation timestamp: {utc_time}")
        logger.info(f"Updated last_agent: {AgentName.HUMAN.value}")
        logger.info("*" * 60)

        return state

    except Exception as e:
        logger.error(f"Error in human handoff: {e}")
        logger.exception("Full traceback:")
        return ctx.context


# =============================================================================
# CALLBACK REGISTRY
# =============================================================================


class CallbackRegistry:
    """
    Registry for managing callback handlers.

    Provides centralized access to all callback handlers and
    allows registration of custom callbacks.
    """

    _handlers = {
        "sales": on_sales_handoff,
        "cta": on_cta_handoff,
        "followup": on_followup_handoff,
        "human": on_human_handoff,
    }

    @classmethod
    def get(cls, name: str):
        """
        Get a callback handler by name.

        Args:
            name: Handler name

        Returns:
            Callback function or None
        """
        return cls._handlers.get(name)

    @classmethod
    def register(cls, name: str, handler):
        """
        Register a custom callback handler.

        Args:
            name: Handler name
            handler: Callback function
        """
        cls._handlers[name] = handler
        logger.debug(f"Registered callback handler: {name}")

    @classmethod
    def list_handlers(cls):
        """
        List all registered handler names.

        Returns:
            List of handler names
        """
        return list(cls._handlers.keys())
