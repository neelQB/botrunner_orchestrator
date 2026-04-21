"""
This module contains tools for the Agents application.
"""


import os
import pytz
from typing import Optional
from datetime import datetime
from pydantic import BaseModel
from agents import function_tool, RunContextWrapper
from rag.retriever.retriever import Retriever

from emailbot.config.settings import logger

from emailbot.core.request_context import get_current_user_id
from emailbot.core.state import BotState


@function_tool
def retrieve_query(ctx: RunContextWrapper[BotState], user_query: str) -> str:
    # Get tenant_id from the state context
    state: BotState = ctx.context
    
    try:
        tenant_id = state.user_context.tenant_id
        logger.info(f"Using collection/tenant_id: {tenant_id}")
    except Exception as e:
        logger.error(f"Error retrieving tenant_id from context: {e}")
    

    logger.info("Tool calling: retrieve_query")
    results = Retriever().retrieve(
        query=user_query,
        tenant_id=tenant_id,
        kb_ids=None,
    )
    return results