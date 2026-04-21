"""
Probing Agent - Generates probing questions for persona refinement.

This agent generates probing questions based on the current
BotPersona to gather additional information from the user.
"""

import os
from opik import track
from typing import Optional

from agents import Agent, ModelSettings, Runner, RunContextWrapper, AgentOutputSchema
from emailbot.core.state import (
    BotPersona,
    ProbingAgentRequest,
    ProbingAgentResponse,
    ProbingQuestion,
    Products,
)

from emailbot.utils.utils import get_consumption_info

from emailbot.config.settings import logger

from emailbot.route.route import RouterModel
from emailbot.prompts import dynamic_probing_instructions
from emailbot.config import settings as _settings

# Load environment variables
# os.getenv("OPENAI_API_KEY")
_settings.openai_api_key

# OPENAI_MODEL_NAME = os.getenv("OPENAI_MODEL_NAME") or ""
OPENAI_MODEL_NAME = _settings.openai_model_name


# Define models using the centralized RouterModel from route.py
primary_model = RouterModel(model="primary")
fallback_model = RouterModel(model="fallback-primary")

# Fallback settings are now managed by the Router in route.py
primary_settings = ModelSettings(prompt_cache_retention="24h")
fallback_settings = ModelSettings(prompt_cache_retention="24h")


def get_probing_agent(persona, tenant_id: Optional[str] = None):
    return Agent(
        name="probing_agent",
        instructions=dynamic_probing_instructions(persona),
        model=RouterModel(model="primary", tenant_id=tenant_id),
        model_settings=primary_settings,
        output_type=AgentOutputSchema(ProbingAgentResponse, strict_json_schema=False),
    )


@track
async def run_probing_agent(persona: BotPersona, total_k: int = 5, comment: str = "", tenant_id: Optional[str] = None):
    try:
        logger.info("|" * 60)
        logger.info(f"Starting Probing Agent with request: {persona}")
        logger.info("|" * 60)
        result = await Runner.run(
            starting_agent=get_probing_agent(persona, tenant_id=tenant_id),
            input=f"total_k {total_k}, comment: {comment}",
            context=RunContextWrapper(persona),
        )
        logger.info("|" * 60)
        logger.info(f"Result of Probing Agent: {result}")
        logger.info("|" * 60)

        output_data = {}
        if hasattr(result.final_output, "model_dump"):
            output_data = result.final_output.model_dump(exclude_unset=True)
        elif hasattr(result.final_output, "__dict__"):
            output_data = {
                k: v for k, v in result.final_output.__dict__.items() if v is not None
            }

        logger.info("|" * 60)
        logger.info(f"Extracted Result from Probing Agent Respnse: {output_data}")
        logger.info("|" * 60)

        questions = output_data.get("questions", [])
        logger.info("|" * 60)
        logger.info(f"Questions: \n{questions}")
        logger.info("|" * 60)

        consumption_data = get_consumption_info(
            raw_responses=result.raw_responses,
            agent_name="probing_agent",
            primary_model=OPENAI_MODEL_NAME,
            tags=["probing"]
        )
        
        output_data["consumption_info"] = consumption_data
        output_data["total_k_generated"] = len(questions)

        return output_data
    except Exception as e:
        logger.error(f"Error Generating Probing Questions: {e}")
        logger.exception("Full traceback:")
        return {"error": f"Error Generating Probing Questions : {str(e)}"}
