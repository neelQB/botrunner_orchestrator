"""
Activity Summary Agent - Consolidates activity summaries from various channels.
"""

from opik import track
from typing import Optional
from agents import Agent, ModelSettings, Runner, RunContextWrapper, AgentOutputSchema

from ai.src.emailsubscriptionbot.core.models import (
    BotPersona,
    ActivitySummary,
    AllSummary
)
from emailbot.config.settings import logger
from emailbot.route.route import RouterModel
from emailbot.prompts.activity_summary_prompt import activity_summary_instructions
from emailbot.config import settings as _settings
from emailbot.emailagents.config import (
    get_primary_model,
    get_model_settings,
    get_output_schema,
)
from ai.src.emailsubscriptionbot.utils.utils import get_consumption_info

OPENAI_MODEL_NAME = _settings.openai_model_name

def get_activity_summary_agent(summaries: AllSummary, tenant_id: Optional[str] = None):
    # Convert activity models to dictionaries for the prompt
    activities = [a.model_dump() for a in summaries.activity]
    
    return Agent(
        name="activity_summary_agent",
        instructions=activity_summary_instructions(
            current_summary=summaries.current_summary or "",
            activities=activities
        ),
        model=get_primary_model(tenant_id=tenant_id),
        model_settings=get_model_settings(),
        output_type=AgentOutputSchema(ActivitySummary, strict_json_schema=False),
    )

@track
async def run_activity_summary_agent(summaries: AllSummary, tenant_id: Optional[str] = None):
    try:
        logger.info("|" * 60)
        logger.info(f"Starting Activity Summary Agent")
        logger.info("|" * 60)
        
        result = await Runner.run(
            starting_agent=get_activity_summary_agent(summaries, tenant_id=tenant_id),
            input="Please generate the main activity summary from the provided channel summaries.",
            context=RunContextWrapper(BotPersona()),
        )
        
        logger.info("|" * 60)
        logger.info(f"Result of Activity Summary Agent: {result}")
        logger.info("|" * 60)

        output_data = {}
        if hasattr(result.final_output, "model_dump"):
            output_data = result.final_output.model_dump(exclude_unset=True)
        elif hasattr(result.final_output, "__dict__"):
            output_data = {
                k: v for k, v in result.final_output.__dict__.items() if v is not None
            }

        logger.info("|" * 60)
        logger.info(f"Extracted Result from Activity Summary Agent Response: {output_data}")
        logger.info("|" * 60)

        consumption_data = get_consumption_info(
            raw_responses=result.raw_responses,
            agent_name="activity_summary_agent",
            primary_model=OPENAI_MODEL_NAME,
            tags=["activity_summary"]
        )
        output_data["consumption_info"] = consumption_data

        return output_data
    except Exception as e:
        logger.error(f"Error Generating Activity Summary: {e}")
        logger.exception("Full traceback:")
        return {"error": f"Error Generating Activity Summary: {str(e)}"}
