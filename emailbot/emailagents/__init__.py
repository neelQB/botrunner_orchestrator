"""
Agents Package - Agent system for OpenAI Agents SDK.

This package provides a complete, modular agent system with:
- Base agent classes and interfaces (base.py)
- Agent factory for creating emailagents (factory.py)
- Agent definitions for all specialized emailagents (definitions.py)
- Handoff callback handlers for agent transitions

Architecture:
    - Individual emailagents are in submodules (sales/, booking/, etc.)
    - Factory pattern centralizes agent creation and caching
    - Base classes enforce consistent interface across emailagents
    - Shared configuration ensures all emailagents use same models/guardrails

Quick Start:
    ```python
    from emailbot.emailagents import create_root_agent, AgentFactory
    
    # Option 1: Create root agent directly (recommended)
    root_agent = create_root_agent()
    result = root_agent.run(state)
    
    # Option 2: Use factory for individual emailagents
    factory = AgentFactory()
    sales_agent = factory.get_sales_agent()
    cta_agent = factory.get_cta_agent()
    ```

Adding New Agents:
    1. Create submodule: emailbot/emailagents/my_agent/__init__.py
    2. Define create_my_agent() function
    3. Import in definitions.py RE-EXPORTS section
    4. Add to factory.py _creators dict
    5. Export here in __all__
"""

from emailbot.emailagents.factory import AgentFactory, create_root_agent
from emailbot.emailagents.definitions import (
    create_sales_agent,
    create_cta_agent,
    create_followup_agent,
    create_human_agent,
    create_lead_analysis_agent,
    create_objection_handle_agent,
    create_negotiation_engine_agent,
    create_asset_sharing_agent,
)

__all__ = [
    # Factory and main entry point
    "AgentFactory",
    "create_root_agent",
    # Individual agent creators (for advanced usage)
    "create_sales_agent",
    "create_cta_agent",
    "create_followup_agent",
    "create_human_agent",
    "create_lead_analysis_agent",
    "create_objection_handle_agent",
    "create_negotiation_engine_agent",
    "create_asset_sharing_agent",
]
