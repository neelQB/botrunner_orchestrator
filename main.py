from fastapi import FastAPI, UploadFile, File, HTTPException, Form, Body
from emailbot.core.state import (
    BotRequest,
    BotState,
    BotResponse,
    BotPersona,
    Products,
    APIResponse,
    ProbingQuestion,
    ProbingRequest,
    AutofillPersonaRequest,
    InstructionAgentRequest,
    TemplateGenerationRequest,
    ExecutiveSummaryRequest,
    ExecutiveSummaryResponse,
    AllSummary,
    ActivitySummary,
    ProbingAgentResponse,
    InstructionAgentResponse,
    TemplateGenerationResponse,
    AutofillPersonaResponse
)
from emailbot.database.session_manager import init_memory_db
from app_agent import run_emailbot_api
from emailbot.utils.utils import convert_to_botstate
from emailbot.config.settings import logger

app = FastAPI(title="This is the main runner for the SDK framework!")

@app.on_event("startup")
def startup_event():
    init_memory_db()
    logger.info("Memory DB initialized at startup")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/cache_stats")
async def get_cache_stats():
    """
    Get prompt cache statistics.

    Returns cache hit rates, token savings, and cost reduction metrics
    from OpenAI's automatic prompt prefix caching.
    """
    from emailbot.utils.prompt_cache import cache_monitor
    return cache_monitor.get_stats()

@app.post("/cache_stats/reset")
async def reset_cache_stats():
    """Reset prompt cache statistics."""
    from emailbot.utils.prompt_cache import cache_monitor
    cache_monitor.reset()
    return {"status": "reset", "message": "Cache statistics have been reset"}

#----------------------------------------------------------------------------#
#-----------------------------CHAT-ENDPOINT----------------------------------#
#----------------------------------------------------------------------------#
# chat endpoint for user query
@app.post("/chat")
async def chat_endpoint(request: BotRequest) -> APIResponse:
    """
    Main chat endpoint that processes user queries through the agent system.

    Returns a dictionary representation of BotState since FastAPI needs
    JSON-serializable response for dataclasses.
    """
    try:
        # Convert request to BotState
        state = convert_to_botstate(request)

        logger.info(
            f"[mainrunner] loaded state for user_id={state.user_context.user_id}"
        )
        logger.info("=" * 100)
        logger.info(f"[mainrunner] state: {state}")
        logger.info(f"[mainrunner] state before running agent: {state}")
        logger.info("=" * 100)

        # Run the agent
        updated_state = await run_emailbot_api(state)

        logger.info(
            f"[mainrunner] saved state for user_id={updated_state.user_context.user_id}"
        )

        # Map BotState to BotResponse for the API response
        # Use model_dump() for Pydantic models instead of asdict() for dataclasses
        context_dict = updated_state.user_context.model_dump()

        logger.info(f"[mainrunner] context_dict user_id: {context_dict.get('user_id')}")
        logger.info(f"[mainrunner] updated_state.response: {updated_state.response}")
        logger.info("--------------------------------------------")
        logger.info(f"[mainrunner] updated_state: {updated_state}")
        logger.info("--------------------------------------------")
        # Create BotResponse with fields from both updated_state.response and user_context
        # Build base fields from user_context
        api_fields = {k: v for k, v in context_dict.items() if k in APIResponse.model_fields}

        # Inject brochure/asset sharing fields from BotState (not in UserContext)
        api_fields["brochure_flag"] = updated_state.brochure_flag
        if updated_state.brochure_details:
            api_fields["asset_shared_details"] = updated_state.brochure_details

        response = APIResponse(
            response=updated_state.response,
            **api_fields,
        )
        logger.info(f"[mainrunner] APIResponse object user_id: {response.user_id}") 
        logger.info("--------------------------------------------")
        logger.info(f"[mainrunner] APIResponse object: {response}")
        logger.info("--------------------------------------------")
        return response

    except Exception as e:
        logger.error(f"[chat_endpoint] Error processing request: {e}")
        logger.exception("Full traceback:")

        # Return a fallback response instead of 500 error
        fallback_response = APIResponse(
            response="I apologize, but I encountered an issue processing your request. Please try again or rephrase your question.",
            user_id=request.user_context.user_id if request.user_context else "",
        )
        return fallback_response

#----------------------------------------------------------------------------#
#---------------------EXECUTIVE-SUMMARY-ENDPOINT-----------------------------#
#----------------------------------------------------------------------------#
@app.post("/generate_executive_summary")
async def generate_executive_summary_endpoint(request: ExecutiveSummaryRequest = Body(...))-> ProbingAgentResponse:
    """
    Standalone endpoint to generate an executive summary on demand.
    Uses agent_result as the primary@app.post("/generate_probing_questions") input; falls back to chat_history if empty.
    No conditions — generates a summary every time it is called.
    """
    from emailbot.database.executive_summary import generate_executive_summary

    try:
        summary, consumption_data = await generate_executive_summary(
            agent_result=request.agent_result,
            chat_history=request.chat_history,
        )
        
        from app.core.models import ConsumptionInfo
        consumption_obj = ConsumptionInfo(**consumption_data) if consumption_data else None

        return ExecutiveSummaryResponse(
            executive_summary=summary, 
            consumption_info=consumption_obj
        )
    except Exception as e:
        logger.error(f"[generate_executive_summary] Error: {e}")
        logger.exception("Full traceback:")
        raise HTTPException(status_code=500, detail=str(e))

# activity summary
@app.post("/activity_summary")
async def activity_summary(request: AllSummary) -> ActivitySummary:
    """
    Endpoint to generate activity summary using the all summary.
    """
    from emailbot.emailagents.activity_summary import run_activity_summary_agent
    logger.info("=" * 100)
    logger.info("Starting activity summary generation")
    logger.info("=" * 100)

    try:
        result = await run_activity_summary_agent(
            summaries=request
        )

        logger.info("=" * 80)
        logger.info(f"Activity summary generated: {result}")
        logger.info("=" * 80)

        activity_summary_text = result.get("activity_summary") if isinstance(result, dict) else result.activity_summary

        # Update state if user_id is provided
        # if request.user_id:
        #     try:
        #         state = get_or_create_session(request.user_id)
        #         if state and state.user_context:
        #             state.user_context.activity_summary = activity_summary_text
        #             logger.info(f"Updated state for user {request.user_id} with activity summary")
        #     except Exception as e:
        #         logger.warning(f"Failed to update state for user {request.user_id}: {e}")

        return ActivitySummary(**result) if isinstance(result, dict) else result

    except Exception as e:
        logger.exception("Error generating activity summary")
        raise


# Generate probing questions
@app.post("/generate_probing_questions")
async def generate_probing_questions(request: ProbingRequest = Body(...))-> ProbingAgentResponse:
    """
    Endpoint to generate probing questions using the probing agent.
    """
    from emailbot.emailagents.probing import run_probing_agent

    logger.info("=" * 100)
    logger.info("Starting probing question generation")
    logger.info("=" * 100)

    try:
        result = await run_probing_agent(
            persona=BotPersona(**(request.custom_persona or {})),
            total_k=request.total_k,
            comment=request.comment or "",
        )

        logger.info("=" * 80)
        logger.info(f"Probing questions generated: {result}")
        logger.info("=" * 80)

        return ProbingAgentResponse(**result)

    except Exception as e:
        logger.exception("Error generating probing questions")
        raise


@app.post("/chat_ui")
async def chat_streamlit(request: BotRequest) -> dict:
    """
    Streamlit UI endpoint that returns the FULL BotState as a dictionary.

    Unlike /chat which returns BotResponse, this returns all fields including:
    - user_context (with last_agent, collected_fields, etc.)
    - bot_persona
    - guardrail_decision
    - response
    """
    from emailbot.core.request_context import set_current_user_id
    from emailbot.utils.utils import convert_to_botstate, model_to_dict

    try:
        # Convert request to BotState
        state = convert_to_botstate(request)

        logger.info(
            f"[chat_ui] Processing request for user_id={state.user_context.user_id}"
        )
        set_current_user_id(state.user_context.tenant_id)
        # Run the agent
        updated_state = await run_emailbot_api(state)

        # Convert full BotState to dict using Pydantic's model_dump
        result = model_to_dict(updated_state)

        logger.info(
            f"[chat_ui] Returning full state with last_agent={result.get('user_context', {}).get('last_agent')}"
        )

        return result

    except Exception as e:
        logger.error(f"[chat_ui] Error processing request: {e}")
        logger.exception("Full traceback:")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------#
# --------------------------------END----------------------------------#
# ---------------------------------------------------------------------#
@app.post("/autofill_persona")
async def autofill_persona(request: AutofillPersonaRequest) -> AutofillPersonaResponse:
    """
    Crawl a website and generate a bot persona based on extracted content.
    Also ingests the cleaned crawled content into the user's Knowledge Base.

    Args:
        request: AutofillPersonaRequest with user_id, URL and crawler parameters

    Returns:
        Dict with pages_analyzed, urls, and bot_persona
    """
    from emailbot.database.session_manager import get_or_create_session

    # If tenant_id is not provided, try to get it from existing session
    current_tenant = request.tenant_id
    if not current_tenant:
        try:
            state = get_or_create_session(request.user_id)
            if state and state.user_context and state.user_context.tenant_id:
                current_tenant = state.user_context.tenant_id
                logger.info(
                    f"[mainrunner] Reusing tenant_id '{current_tenant}' from session for user '{request.user_id}'"
                )
        except Exception as e:
            logger.warning(
                f"[mainrunner] Could not retrieve session for user '{request.user_id}': {e}"
            )

    try:
        # Lazy import to speed up server startup
        from emailbot.emailagents.crawl_persona import run_crawl_persona_agent
 
        result = await run_crawl_persona_agent(
            url=request.url,
            user_id=request.user_id,
            tenant_id=current_tenant,
            max_depth=request.max_depth,
            max_pages=request.max_pages,
            max_tokens=request.max_tokens,
            max_products=request.max_products,
        )
        logger.info("*" * 80)
        logger.info(f"Generated Autofill persona: {result}")
        logger.info("*" * 80)
        return AutofillPersonaResponse(**result)
    except Exception as e:
        logger.error(f"[autofill_persona] Error processing request: {e}")
        logger.exception("Full traceback:")
        raise HTTPException(status_code=500, detail=str(e))

# Generate instructions for probing
@app.post("/generate_instructions")
async def generate_probing_instructions_endpoint(
    request: InstructionAgentRequest = Body(...),
) -> InstructionAgentResponse:
    """
    Generate probing instruction suggestions based on the current persona.
    """
    custom_persona = request.custom_persona or {}
    max_instructions = request.max_instructions

    try:
        # Lazy import to speed up server startup
        from emailbot.emailagents.probing_instruction import generate_probing_question_instructions
 
        persona = BotPersona(**custom_persona) if custom_persona else None
        logger.info("*" * 80)
        logger.info(
            f"Generating instructions for persona: {persona}, max_instructions: {max_instructions}"
        )
        logger.info("*" * 80)
        result = await generate_probing_question_instructions(
            persona=persona, max_instructions=max_instructions
        )
        logger.info(f"Generated instructions: {result}")
        logger.info("*" * 80)
        return InstructionAgentResponse(**result)
    except Exception as e:
        logger.error(f"[generate_probing_instructions] Error: {e}")
        logger.exception("Full traceback:")
        raise HTTPException(status_code=500, detail=str(e))

# Generate templates for each product
@app.post("/generate_templates")
async def generate_templates_endpoint(request: TemplateGenerationRequest = Body(...)) -> TemplateGenerationResponse:
    """
    Generate Templates for each product.
    """
    custom_persona = request.custom_persona or {}
    max_products = request.max_products

    try:
        # Lazy import to speed up server startup
        from emailbot.emailagents.template_generation import run_template_generation_agent
 
        persona = BotPersona(**custom_persona) if custom_persona else None

        logger.info("*" * 80)
        logger.info(
            f"Generating templates for persona: {persona}, max_products: {max_products}"
        )
        logger.info("*" * 80)
        result = await run_template_generation_agent(
            persona=persona, max_products=max_products
        )
        logger.info(f"Generated templates: {result}")
        logger.info("*" * 80)
        return TemplateGenerationResponse(**result)
    except Exception as e:
        logger.error(f"[generate_templates] Error: {e}")
        logger.exception("Full traceback:")
        raise HTTPException(status_code=500, detail=str(e))
