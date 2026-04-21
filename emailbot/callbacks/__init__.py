"""
Callbacks Package - Handoff callback handlers for agent transitions.

This package provides callback handlers that are executed when
an agent hands off control to another agent.

Usage:
    from emailbot.callbacks import on_sales_handoff, on_cta_handoff
    
    handoff(agent=sales_agent, on_handoff=on_sales_handoff)
"""

from emailbot.callbacks.handlers import (
    on_sales_handoff,
    on_cta_handoff,
    on_followup_handoff,
    on_human_handoff,
)

__all__ = [
    "on_sales_handoff",
    "on_cta_handoff",
    "on_followup_handoff",
    "on_human_handoff",
]
