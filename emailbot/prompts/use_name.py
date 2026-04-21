from emailbot.core.state import BotState


from emailbot.config.settings import logger


def use_name(state: BotState):

    use_name = state.bot_persona.use_name_reference
    logger.info(f"name usage flag: {use_name}")

    name = (
        state.user_context.contact_details.name
        if state.user_context.contact_details
        and state.user_context.contact_details.name
        else ""
    )
    if use_name == True:
        name_usage_rules = f"""
        USER NAME USAGE RULES:
        - User Name: "{name}".
        - Rephrase the user name if it has any symbols or numbers, and only keep the first name if it has multiple words.
        - Use User Name: Active
        - You may use the User Name naturally and sparingly in responses when appropriate.
        - Never overuse, repeat, or fabricate the User name.
        - If the User name is empty, do NOT reference it at all.
        """
    else:
        name_usage_rules = f"""
        USER NAME USAGE RULES:
        - User Name: "{name}".
        - Rephrase the user name if it has any symbols or numbers, and only keep the first name if it has multiple words.
        - Use User Name: Disabled
        - Use the User Name ONLY in the initial greeting.
        - Do NOT use the User Name again after the greeting.
        - If the User name is empty, do NOT reference it at all.
        """

    return name_usage_rules
