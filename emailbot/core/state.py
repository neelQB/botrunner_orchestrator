"""
State Module - Backward compatibility re-exports.

This module re-exports all models from emailbot.core.models for backward
compatibility. New code should import directly from emailbot.core.models.

DEPRECATED: Import directly from emailbot.core.models instead.

Example (old way - still works):
    from emailbot.core.state import BotState, UserContext
    
Example (new way - preferred):
    from emailbot.core.models import BotState, UserContext

Note: All dataclasses have been converted to Pydantic models.
The interface remains the same, but now includes:
- Automatic validation
- Better serialization
- Field validators
- Model methods
"""

# Re-export all models for backward compatibility
from emailbot.core.models import (
    # Products
    Products,
    # Assets
    Asset,
    AssetSharedDetails,
    # Guardrails
    InputGuardrail,
    OutputGuardrail,
    # Contact & Leads
    CollectedFields,
    ContactDetails,
    Leads,
    LeadAnalysis,
    # Probing
    ProbingQuestion,
    ProbingContext,
    ProbingOutput,
    ObjectionState,
    # Followup & Email
    FollowupDetails,
    EmailTemplate,
    ProceedEmailDetails,
    # Booking
    BookingFields,
    HumanDetails,
    # Bot Core
    BotPersona,
    UserContext,
    BotState,
    BotResponse,
    # API
    UserContextRequest,
    BotRequest,
    APIResponse,
    # Probing Agent
    ProbingAgentRequest,
    ProbingAgentResponse,
    # Generate Probing API
    ProbingRequest,
    # Autofill
    AutofillPersonaRequest,
    AutofillPersonaResponse,
    # Instruction Agent
    InstructionAgentRequest,
    InstructionAgentResponse,
    # Template Generation Agent
    TemplateGenerationRequest,
    TemplateGenerationResponse,
    WhatsAppTemplate,
    TemplateButton,
    # Pricing
    NegotiationAgentResponse,
    NegotiationConfig,
    NegotiationState,
    # Executive Summary
    ExecutiveSummaryRequest,
    ExecutiveSummaryResponse,
    # Activity Summary
    ActivitySummary,
    AllSummary,
    # Handoff
    HandoffArgs
)

# Define __all__ for explicit exports
__all__ = [
    # Products
    "Products",
    # Assets
    "Asset",
    "AssetSharedDetails",
    # Guardrails
    "InputGuardrail",
    "OutputGuardrail",
    # Contact & Leads
    "CollectedFields",
    "ContactDetails",
    "Leads",
    "LeadAnalysis",
    # Probing
    "ProbingQuestion",
    "ProbingContext",
    "ProbingOutput",
    "ObjectionState",
    # Followup & Email
    "FollowupDetails",
    "EmailTemplate",
    "ProceedEmailDetails",
    # Booking
    "BookingFields",
    "HumanDetails",
    # Bot Core
    "BotPersona",
    "UserContext",
    "BotState",
    "BotResponse",
    # API
    "UserContextRequest",
    "BotRequest",
    "APIResponse",
    # Probing Agent
    "ProbingAgentRequest",
    "ProbingAgentResponse",
    # Probing Agent API
    "ProbingRequest",
    # Autofill
    "AutofillPersonaRequest",
    "AutofillPersonaResponse",
    # Instruction Agent
    "InstructionAgentRequest",
    "InstructionAgentResponse",
    # Template Generation Agent
    "TemplateGenerationRequest",
    "TemplateGenerationResponse",
    "WhatsAppTemplate",
    "TemplateButton",
    # Pricing
    "NegotiationAgentResponse",
    "NegotiationConfig",
    "NegotiationState",
    # Executive Summary
    "ExecutiveSummaryRequest",
    "ExecutiveSummaryResponse",
    # Activity Summary
    "ActivitySummary",
    "AllSummary",
    # Handoff
    "HandoffArgs"
]
