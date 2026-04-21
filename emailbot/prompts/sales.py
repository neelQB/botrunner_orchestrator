from emailbot.core import state


from emailbot.config.settings import logger
from emailbot.core.state import BotState
from emailbot.prompts.probing import probing_engine_prompt
from emailbot.prompts.dynamic_sales import sales_engine_prompt


def sales_prompt(state: BotState) -> str:
    # PROBING, Sales ENGINE & CTA LOGIC
    enable_probing = getattr(state.bot_persona, "enable_probing", False)
    not_probing_completed = not getattr(
        state.probing_context, "probing_completed", False
    )
    not_objection_limit_reached = not getattr(
        state.objection_state, "is_objection_limit_reached", False
    )
    is_objection = getattr(state.probing_context, "is_objection", False)

    # Log objection status
    logger.info(f"Is in objection state: {is_objection}")
    logger.info(f"Is objection limit reached: {not_objection_limit_reached}")
    logger.info("-------------STATE----------")
    logger.info(state.probing_context)
    logger.info("----------------------------")
    logger.info(state.objection_state)
    logger.info("----------------------------")
    if is_objection:
        logger.info("------------------")
        logger.info("OBJECTION DETECTED")
    # End Log objection status

    # If probing is enabled and not yet completed and no objection limit reached.
    if enable_probing and not_probing_completed and not_objection_limit_reached:
        return probing_engine_prompt(state)
    else:
        return sales_engine_prompt(state)
