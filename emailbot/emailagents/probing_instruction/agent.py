"""
Probing Instruction Agent
=========================
Generates instruction suggestions for the probing question generation agent.
"""

import litellm
from opik import track
from agents import Agent, Runner, set_trace_processors, AgentOutputSchema
from agents.extensions.models.litellm_model import LitellmModel
from opik.integrations.litellm import track_completion
from opik.integrations.openai.agents import OpikTracingProcessor
from emailbot.core.state import BotPersona
from emailbot.core.models import InstructionAgentResponse
from emailbot.prompts.generate_probing_instructions import (
    get_probing_instructions_agent_prompt,
)
from emailbot.config.settings import logger
from emailbot.utils.utils import get_consumption_info

# Opik Tracing Setup
litellm.acompletion = track_completion()(litellm.acompletion)
set_trace_processors([OpikTracingProcessor()])


@track
async def generate_probing_question_instructions(
    persona: BotPersona = None, max_instructions: int = 5
):
    try:
        generate_probing_question_agent = Agent(
            name="probing_instruction_agent",
            instructions=get_probing_instructions_agent_prompt(max_instructions),
            model=LitellmModel(model="gemini/gemini-3-flash-preview"),
            output_type=AgentOutputSchema(InstructionAgentResponse, strict_json_schema=False),
        )

        agent_result = await Runner.run(
            starting_agent=generate_probing_question_agent,
            input=str(persona) if persona else "",
        )

        extracted_instructions = agent_result.final_output
        if hasattr(extracted_instructions, "model_dump"):
            extracted_instructions = extracted_instructions.model_dump()

        consumption_data = get_consumption_info(
            raw_responses=agent_result.raw_responses,
            agent_name="probing_instruction_agent",
            primary_model="gemini/gemini-3-flash-preview",
            tags=["probing_instruction"]
        )

        return {"instructions": extracted_instructions.get('instructions', extracted_instructions) if isinstance(extracted_instructions, dict) else extracted_instructions, "consumption_info": consumption_data}
    except Exception as e:
        logger.error(f"Error in generate_probing_question_instructions: {e}")
        return {"error": str(e), "instructions": []}