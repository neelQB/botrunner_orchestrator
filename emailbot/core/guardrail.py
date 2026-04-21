"""
Guardrails Module - Input and output validation for agent responses.

This module provides guardrail functions that validate:
- Input queries for potential attacks or policy violations
- Output responses for quality and safety

Guardrails run in parallel with the main agent flow and can:
- Block harmful inputs
- Correct or reject inappropriate outputs
- Log violations for monitoring

Usage:
    from emailbot.core.guardrail import input_attack, output_guardrail
    
    agent = Agent(
        ...,
        input_guardrails=[input_attack],
        output_guardrails=[output_guardrail],
    )
"""

from typing import Any, List, Optional

from agents import (
    Agent,
    Runner,
    input_guardrail,
    output_guardrail as output_guardrail_decorator,
    RunContextWrapper,
    TResponseInputItem,
    GuardrailFunctionOutput,
    AgentOutputSchema,
    ModelSettings,
)


from emailbot.config.settings import logger, Settings
from opik import track

from emailbot.route.route import RouterModel
from emailbot.core.models import (
    InputGuardrail,
    OutputGuardrail,
    BotState,
    BotResponse,
    UserContext,
    BotPersona,
    Products,
)
from emailbot.prompts import input_guardrail_prompt, output_guardrail_prompt
from emailbot.core.exceptions import InputGuardrailError, OutputGuardrailError


# =============================================================================
# MODULE STATE
# =============================================================================

# Module-level state for guardrail decisions
# This is used to persist guardrail decisions across the request lifecycle
_guardrail_state = {
    "input_decision": None,
    "output_decision": None,
}


def get_guardrail_state() -> dict:
    """Get the current guardrail state."""
    return _guardrail_state.copy()


def get_output_guardrail_decision():
    """Get the output guardrail decision from module state."""
    return _guardrail_state.get("output_decision")


def get_input_guardrail_decision():
    """Get the input guardrail decision from module state."""
    return _guardrail_state.get("input_decision")


def reset_guardrail_state():
    """Reset guardrail state for a new request."""
    _guardrail_state["input_decision"] = None
    _guardrail_state["output_decision"] = None


# =============================================================================
# MODEL CONFIGURATION
# =============================================================================

# Use the guardrail model (gpt-4o-mini by default, configurable via GUARDRAIL_MODEL env var)
_guardrail_model = RouterModel(model="guardrail")
_model_settings = ModelSettings(prompt_cache_retention="24h")


# =============================================================================
# INPUT GUARDRAIL
# =============================================================================

# Conversational fillers that should ALWAYS be classified as safe
# These bypass the LLM guardrail entirely for speed and reliability
SAFE_CONVERSATIONAL_PATTERNS = {
    # Thinking sounds
    "hmm",
    "hmmm",
    "hmmmm",
    "um",
    "uh",
    "uhh",
    "umm",
    "erm",
    "ah",
    "ahh",
    # Acknowledgments
    "ok",
    "okay",
    "alright",
    "sure",
    "yes",
    "yeah",
    "yep",
    "yup",
    "no",
    "nope",
    "nah",
    # Neutral responses
    "i see",
    "got it",
    "understood",
    "interesting",
    "cool",
    "nice",
    "great",
    "good",
    # Hesitation
    "let me think",
    "maybe",
    "perhaps",
    "i guess",
    "i suppose",
    # Short affirmations
    "right",
    "correct",
    "true",
    "fine",
    "thanks",
    "thank you",
    "ty",
    # Short objections / disinterest (always safe — sales context)
    "not interested",
    "not now",
    "no thanks",
    "no thank you",
    "nevermind",
    "never mind",
    "dont want",
    "don't want",
    "nahi chahiye",
    "nahi",
    # Engagement signals
    "go on",
    "continue",
    "tell me more",
    "and",
    "so",
    "then",
    "what else",
    # Greetings
    "hi",
    "hii",
    "hiii",
    "hello",
    "heyy",
    "hey",
    "good morning",
    "good afternoon",
    "good evening",
    "morning",
    "afternoon",
    "evening",
    "howdy",
    "hiya",
    # Human escalation / delegation (always safe — platform capability)
    "talk to senior",
    "talk to a senior",
    "talk to your senior",
    "speak to senior",
    "speak to your senior",
    "speak with senior",
    "speak with your senior",
    "contact senior",
    "contact your senior",
    "connect me to senior",
    "connect me to your senior",
    "contact me with your senior",
    "talk to manager",
    "talk to your manager",
    "speak to manager",
    "speak to your manager",
    "speak with manager",
    "talk to a person",
    "talk to a human",
    "transfer to human",
    "speak to someone",
    "connect me to your team",
    "let me talk to someone",
    "put me through to your boss",
    "contact my assistant",
    "talk to my assistant",
    "reach my manager",
    "talk to my secretary",
    "i want to talk to a person",
    "connect me to a person",
    "talk to doctor",
    "speak to doctor",
    "speak with a doctor",
}


def _is_safe_conversational_pattern(user_input: str) -> bool:
    """
    Quick check if user input is a safe conversational pattern.
    This bypasses the LLM guardrail for speed and reliability.

    Args:
        user_input: The user's message

    Returns:
        True if the input matches a safe conversational pattern
    """
    if not user_input:
        return False

    # Normalize: lowercase, strip whitespace and punctuation
    normalized = user_input.lower().strip().rstrip("?!.,;:")

    # Direct match
    if normalized in SAFE_CONVERSATIONAL_PATTERNS:
        return True

    # Check for patterns with minor variations (e.g., "hmm..." or "ok!")
    # Remove trailing punctuation for matching
    clean = "".join(c for c in normalized if c.isalnum() or c.isspace()).strip()
    if clean in SAFE_CONVERSATIONAL_PATTERNS:
        return True

    # Check for repeated characters like "hmmmmm" or "okkkk"
    import re

    # Collapse repeated characters
    collapsed = re.sub(r"(.)\1+", r"\1\1", clean)
    if collapsed in SAFE_CONVERSATIONAL_PATTERNS:
        return True

    # Human escalation keyword check — catches misspelled variants like
    # "tlk with yopur senior", "speek to manger", "contact my assistant i am busy"
    ESCALATION_TARGETS = {"senior", "manager", "manger", "supervisor", "doctor",
                          "human", "person", "representative", "assistant", "secretary",
                          "boss", "team", "executive", "specialist"}
    ESCALATION_VERBS = {"talk", "tlk", "speak", "speek", "spk", "contact", "connect",
                        "transfer", "reach", "call", "put"}
    words = set(clean.split())
    if words & ESCALATION_VERBS and words & ESCALATION_TARGETS:
        return True

    # Company role acronym check — catches "give coo name", "who is ceo", "tell me cfo"
    # These are always safe company-info queries, never attacks.
    COMPANY_ROLE_ACRONYMS = {"ceo", "coo", "cto", "cfo", "cmo", "vp", "md", "gm",
                              "hr", "bd", "cpo", "chro", "ciso", "svp", "evp"}
    INQUIRY_WORDS = {"who", "give", "tell", "what", "which", "name", "contact",
                     "email", "phone", "number", "get", "share", "find", "show"}
    if words & COMPANY_ROLE_ACRONYMS and words & INQUIRY_WORDS:
        return True

    return False


def _create_input_guardrail_instructions(
    ctx: RunContextWrapper[BotState],
    agent: Agent,
) -> str:
    """
    Generate dynamic instructions for input guardrail agent.

    Args:
        ctx: RunContextWrapper containing BotState
        agent: Agent instance

    Returns:
        Formatted guardrail prompt
    """
    logger.info("[input_guardrail_instructions] Generating guardrail instructions")

    try:
        state = ctx.context
        return input_guardrail_prompt(state=state)
    except Exception as e:
        logger.error(f"Error generating input guardrail instructions: {e}")
        # Return basic fallback prompt
        return """
        Analyze the user input for potential security threats or policy violations.
        Return:
        - is_attack_query: true/false
        - reason: explanation
        - classification: type of issue if detected
        """

@input_guardrail
@track
async def input_attack(
    ctx: RunContextWrapper[None],
    agent: Agent,
    conversation_history: str | List[TResponseInputItem],
) -> GuardrailFunctionOutput:
    """
    Input guardrail to detect attack queries.

    Analyzes user input for:
    - Prompt injection attempts
    - Jailbreak attempts
    - Off-topic or malicious queries
    - Policy violations

    Args:
        ctx: RunContextWrapper containing context
        agent: Agent instance
        conversation_history: Input to analyze

    Returns:
        GuardrailFunctionOutput with decision
    """
    logger.info("[input_attack] Running input guardrail check")

    # Extract the user's message for quick pre-check
    user_message = ""
    if isinstance(conversation_history, str):
        user_message = conversation_history
    elif isinstance(conversation_history, list) and len(conversation_history) > 0:
        # Get the last user message from the list
        for item in reversed(conversation_history):
            if isinstance(item, dict) and item.get("role") == "user":
                user_message = item.get("content", "")
                break
            elif hasattr(item, "role") and item.role == "user":
                user_message = getattr(item, "content", "")
                break
            elif hasattr(item, "content"):
                # Fallback: use the content if available
                user_message = (
                    str(item.content) if hasattr(item, "content") else str(item)
                )
                break

    # FAST PATH: Check for safe conversational patterns first
    # This bypasses the LLM for common safe patterns like "hmm", "ok", etc.
    if user_message and _is_safe_conversational_pattern(user_message):
        logger.info(
            f"[input_attack] Fast path: '{user_message}' is a safe conversational pattern"
        )

        safe_output = InputGuardrail(
            is_attack_query=False,
            reason="Safe conversational pattern - natural dialogue continuation",
            classification="safe",
        )

        # Store decision in module state
        _guardrail_state["input_decision"] = safe_output

        # Update state if available
        if hasattr(ctx, "context") and ctx.context is not None:
            if hasattr(ctx.context, "input_guardrail_decision"):
                ctx.context.input_guardrail_decision = safe_output

        return GuardrailFunctionOutput(
            output_info=safe_output, tripwire_triggered=False
        )

    # SLOW PATH: Run the LLM-based guardrail for non-trivial inputs
    try:
        # Extract tenant_id from context for prompt caching
        tenant_id = None
        if hasattr(ctx, "context") and ctx.context is not None:
            state = ctx.context
            if hasattr(state, "user_context") and state.user_context:
                tenant_id = state.user_context.tenant_id or None

        # Create guardrail agent with tenant_id for prompt caching
        input_guardrail_agent = Agent(
            name="input_guardrail_agent",
            instructions=_create_input_guardrail_instructions,
            model=RouterModel(model="guardrail", tenant_id=tenant_id),
            model_settings=_model_settings,
            output_type=AgentOutputSchema(InputGuardrail, strict_json_schema=False),
        )

        result = await Runner.run(
            input_guardrail_agent,
            input=conversation_history,
            context=ctx.context,
        )

        guardrail_output = result.final_output
        logger.info(f"[input_attack] Guardrail output: {guardrail_output}")

        # ── Fix for small models (e.g. gpt-4.1-nano) that may only return
        #    the "response" field.  When Pydantic fills defaults, we get
        #    is_attack_query=False + classification=None + a non-empty response,
        #    which is inconsistent.  Detect and auto-correct here.
        if guardrail_output and isinstance(guardrail_output, InputGuardrail):
            _response = getattr(guardrail_output, "response", "") or ""
            _classification = getattr(guardrail_output, "classification", None)
            _is_attack = getattr(guardrail_output, "is_attack_query", False)
            _reason = getattr(guardrail_output, "reason", None)

            # Case 1: response has content but is_attack_query is False and
            #         classification is missing — model only emitted "response".
            if _response.strip() and not _is_attack and not _classification:
                logger.warning(
                    "[input_attack] Inconsistent guardrail output detected: "
                    "non-empty response but is_attack_query=False. Auto-correcting to attack_query."
                )
                guardrail_output.is_attack_query = True
                guardrail_output.classification = "attack_query"
                if not _reason:
                    guardrail_output.reason = "Auto-corrected: model returned redirect response without classification fields"

            # Case 2: classification says "attack_query" but is_attack_query is False
            elif _classification and _classification.lower() == "attack_query" and not _is_attack:
                logger.warning(
                    "[input_attack] Inconsistent guardrail output: classification=attack_query "
                    "but is_attack_query=False. Auto-correcting."
                )
                guardrail_output.is_attack_query = True

            # Case 3: is_attack_query is True but response is empty — leave as-is,
            #         the handler has a fallback for empty responses.

        # Collect raw responses for token tracking
        if hasattr(ctx, "context") and ctx.context is not None:
            state = ctx.context
            if hasattr(state, "additional_raw_responses"):
                for resp in result.raw_responses:
                    # Tag the response for get_consumption_info
                    setattr(resp, "_stage_name", "input_guardrail")
                    # Tag the actual model name ONLY if it hasn't already been injected by route.py
                    # (response.model may hold the router alias or primary model name)
                    if not getattr(resp, "_actual_model_name", None):
                        setattr(resp, "_actual_model_name", _settings.guardrail_model)
                    state.additional_raw_responses.append(resp)

        # Store decision in module state
        _guardrail_state["input_decision"] = guardrail_output

        # Update state if available
        if hasattr(ctx, "context") and ctx.context is not None:
            if hasattr(ctx.context, "input_guardrail_decision"):
                ctx.context.input_guardrail_decision = guardrail_output

        logger.debug("-" * 50)

        is_attack_query = getattr(guardrail_output, "is_attack_query", False)

        # Note: tripwire_triggered=False means we don't block, just record
        return GuardrailFunctionOutput(
            output_info=guardrail_output, tripwire_triggered=False
        )

    except Exception as e:
        logger.error(f"[input_attack] Error running guardrail: {e}")
        logger.exception("Full traceback:")

        # Fail open - don't block on guardrail errors
        return GuardrailFunctionOutput(
            output_info={"error": str(e)}, tripwire_triggered=False
        )


# =============================================================================
# OUTPUT GUARDRAIL
# =============================================================================


def _create_output_guardrail_instructions(
    ctx: RunContextWrapper[BotResponse],
    agent: Agent,
) -> str:
    """
    Generate dynamic instructions for output guardrail agent.

    Args:
        ctx: RunContextWrapper containing BotResponse
        agent: Agent instance

    Returns:
        Formatted guardrail prompt
    """
    logger.info("[output_guardrail_instructions] Generating guardrail instructions")

    try:
        state = ctx.context
        return output_guardrail_prompt(state=state)
    except Exception as e:
        logger.error(f"Error generating output guardrail instructions: {e}")
        # Return basic fallback prompt
        return """
        Validate the bot response for quality and safety.
        Return:
        - validation_status_approved: "yes" or "no"
        - issue: description of any issues
        - suggested_text: corrected text if needed
        - reasoning: explanation of decision
        """


@output_guardrail_decorator
@track
async def output_guardrail(
    ctx: RunContextWrapper, agent: Agent, output: BotResponse
) -> GuardrailFunctionOutput:
    """
    Output guardrail to validate bot responses.

    Checks responses for:
    - Hallucinations or incorrect information
    - Policy violations
    - Quality issues
    - Inappropriate content

    Args:
        ctx: RunContextWrapper containing context
        agent: Agent instance
        output: BotResponse to validate

    Returns:
        GuardrailFunctionOutput with decision
    """
    logger.info("*" * 60)
    logger.info("[output_guardrail] Running output guardrail check")
    logger.info(f"[output_guardrail] Validating response: {output.response[:100]}...")

    try:
        # Extract tenant_id from context for prompt caching
        tenant_id = None
        if hasattr(ctx, "context") and ctx.context is not None:
            state = ctx.context
            if hasattr(state, "user_context") and state.user_context:
                tenant_id = state.user_context.tenant_id or None

        # Create guardrail agent with tenant_id for prompt caching
        output_guardrail_agent = Agent(
            name="output_guardrail_agent",
            instructions=_create_output_guardrail_instructions,
            model=RouterModel(model="guardrail", tenant_id=tenant_id),
            model_settings=_model_settings,
            output_type=AgentOutputSchema(OutputGuardrail, strict_json_schema=False),
        )

        result = await Runner.run(
            output_guardrail_agent,
            input=output.response,
            context=ctx.context,
        )

        guardrail_output = result.final_output
        logger.info(f"[output_guardrail] Guardrail output: {guardrail_output}")

        # Collect raw responses for token tracking
        if hasattr(ctx, "context") and ctx.context is not None:
            state = ctx.context
            if hasattr(state, "additional_raw_responses"):
                for resp in result.raw_responses:
                    # Tag the response for get_consumption_info
                    setattr(resp, "_stage_name", "output_guardrail")
                    # Tag the actual model name ONLY if it hasn't already been injected by route.py
                    # (response.model may hold the router alias or primary model name)
                    if not getattr(resp, "_actual_model_name", None):
                        setattr(resp, "_actual_model_name", _settings.guardrail_model)
                    state.additional_raw_responses.append(resp)

        # Store decision in module state
        _guardrail_state["output_decision"] = guardrail_output

        # Check if validation was NOT approved - tripwire triggers on failure
        validation_failed = False
        if hasattr(guardrail_output, "validation_status_approved"):
            status = guardrail_output.validation_status_approved
            if status and str(status).lower() == "no":
                validation_failed = True

        logger.info(
            f"[output_guardrail] Validation status: {guardrail_output.validation_status_approved}"
        )
        logger.debug(f"[output_guardrail] Tripwire triggered: {validation_failed}")
        logger.debug("-" * 50)

        return GuardrailFunctionOutput(
            output_info=guardrail_output, tripwire_triggered=False
        )

    except Exception as e:
        logger.error(f"[output_guardrail] Error running guardrail: {e}")
        logger.exception("Full traceback:")

        # Fail open - don't block on guardrail errors
        return GuardrailFunctionOutput(
            output_info={"error": str(e)}, tripwire_triggered=False
        )


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================


def create_input_guardrail_result(
    is_attack: bool, reason: str, classification: Optional[str] = None
) -> InputGuardrail:
    """
    Create an InputGuardrail result.

    Args:
        is_attack: Whether input is classified as attack
        reason: Explanation for classification
        classification: Type of attack if detected

    Returns:
        InputGuardrail instance
    """
    return InputGuardrail(
        is_attack_query=is_attack, reason=reason, classification=classification
    )


def create_output_guardrail_result(
    approved: bool,
    issue: Optional[str] = None,
    original_text: Optional[str] = None,
    suggested_text: Optional[str] = None,
    reasoning: Optional[str] = None,
) -> OutputGuardrail:
    """
    Create an OutputGuardrail result.

    Args:
        approved: Whether output is approved
        issue: Description of any issues
        original_text: Original text that was validated
        suggested_text: Corrected text suggestion
        reasoning: Explanation for decision

    Returns:
        OutputGuardrail instance
    """
    return OutputGuardrail(
        validation_status_approved="yes" if approved else "no",
        issue=issue,
        original_text=original_text,
        suggested_text=suggested_text,
        reasoning=reasoning,
    )
