from emailbot.core.state import BotState


from emailbot.config.settings import logger


def use_emoji(state: BotState) -> str:
    use_emoji = state.bot_persona.use_emoji
    logger.info(f"emoji usage flag: {use_emoji}")

    if use_emoji == True:
        emoji_usage_rules = """
      ### EMOJI USAGE RULES:
      - Emoji: Active.
      - Principle: Select emojis that maintain a professional business tone.
      - Contextual Relevance: Use emojis that visually represent concrete objects or professional actions (e.g., 📅 for meetings, ✉️ for messages, 😀 or 😊 for casual uses or confirm CTA).
      - Negative Constraints: 
        - NEVER use informal reaction emojis like 🤔, 🤨, 🙄, 🤫, 🤬, 👨‍👩‍👦, 👗, 🦝, 🎈 or 🤡.
        - Strictly avoid "thinking" or "puzzled" expressions.
      - Emojis are allowed ONLY in conversational, sales, or action responses, followup, CTA.
      - Do NOT use emojis in neutral, system, instructional, or error responses.
      - Ensure emojis are subtle and enhance the professional message rather than distracting from it.
      - do not overuse emojis. use them only when necessary.
      """
    else:
        emoji_usage_rules = """
      ### EMOJI USAGE RULES:
      - Emoji: Disabled.
      - Emojis are strictly forbidden in all responses, without exception.
      """

    return emoji_usage_rules
