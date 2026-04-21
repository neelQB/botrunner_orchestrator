"""
Instructions Package - Dynamic instruction generation for emailagents.

This package provides instruction generators that create dynamic
prompts based on conversation state and context.

Usage:
    from emailbot.instructions import InstructionBuilder
    
    builder = InstructionBuilder(state)
    prompt = builder.build_main_instructions()
"""

from emailbot.instructions.generators import (
    InstructionBuilder,
    build_main_instructions,
    build_sales_instructions,
    build_followup_instructions,
    build_human_instructions,
)

__all__ = [
    "InstructionBuilder",
    "build_main_instructions",
    "build_sales_instructions",
    "build_followup_instructions",
    "build_human_instructions",
]
