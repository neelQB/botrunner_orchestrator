"""
Core Data Models - Pydantic models for the application.

This module contains all Pydantic models that define the data structures
used throughout the application. All models include validation, serialization,
and proper type hints.

Models are organized by domain:
- Products: Product-related models
- Contact: Contact and lead information
- Booking: Booking workflow models
- Probing: Probing question models
- Guardrail: Input/output guardrail models
- Bot: Main bot state and persona models
- API: Request/response models

Usage:
    from emailbot.core.models import BotState, UserContext, BotPersona
    
    state = BotState(
        user_context=UserContext(user_id="123"),
        bot_persona=BotPersona(name="Arya", company_name="AI Sante")
    )
"""
import uuid as _uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Union, Literal
from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict
from emailbot.config.settings import logger
import math as _math
from emailbot.config.constants import (
    BookingType,
    LeadClassification,
    UrgencyLevel,
    DEFAULT_PROBING_THRESHOLD,
    DEFAULT_OBJECTION_LIMIT,
    DEFAULT_RESET_COUNT_LIMIT,
)

def _safe_float(v: Any, default: float = 0.0) -> float:
    """Return *v* as a finite float; replace NaN / Inf with *default*."""
    if v is None:
        return default
    try:
        f = float(v)
        if _math.isnan(f) or _math.isinf(f):
            return default
        return f
    except (TypeError, ValueError):
        return default
# =============================================================================
# PRODUCT MODELS
# =============================================================================

class Plan(BaseModel):
    """
    Pricing plan model.

    Attributes:
        id: Unique plan identifier
        name: Plan display name
        description: Plan description
        billing_cycle: Billing cycle (e.g. monthly, yearly)
        redirect_url: URL to redirect to after plan selection
        features: List of features included in the plan
        base_price: Base price of the plan before discounts and taxes
        tax: Tax percentage for the plan
        discount: Discount percentage for the plan
        total_price: Total price of the plan after applying discounts and taxes
    """

    id: str = Field(..., description="Unique plan identifier")
    name: str = Field(..., description="Plan display name")
    description: Optional[str] = Field(default=None, description="Plan description")
    billing_cycle: Optional[str] = Field(
        default=None, description="Billing cycle (e.g. monthly, yearly)", values="Monthly, Yearly, One-time, Quarterly"
    )
    redirect_url: Optional[str] = Field(default=None, description="URL to redirect to after plan selection")
    features: List[str] = Field(default_factory=list, description="List of features included in the plan")
    base_price: Optional[float] = Field(default=None, description="Base price of the plan")
    tax: Optional[float] = Field(default=None, description="Tax percentage for the plan")
    discount: Optional[float] = Field(default=0.0, description="Discount percentage for the plan")
    total_price: Optional[float] = Field(default=None, description="Total price of the plan")

class Products(BaseModel):
    """
    Product information model.

    Attributes:
        id: Unique product identifier
        name: Product display name
        description: Product description
        base_pricing: Base price of the product
        currency: Currency for the pricing
        max_discount_percent: Maximum discount percentage allowed for this product
        plans: List of pricing plans for this product
    """

    id: str = Field(..., description="Unique product identifier")
    name: str = Field(..., description="Product display name")
    description: str = Field(default="", description="Product description")
    base_pricing: Optional[float] = None
    currency: Optional[str] = "INR"
    max_discount_percent: Optional[float] = 0.0
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )
    plans: Optional[List[Plan]] = Field(
        default_factory=list, description="List of pricing plans for this product"
    )


class Asset(BaseModel):
    """
    Shareable asset model (brochures, PDFs, documents, files).

    Attributes:
        asset_id: Unique asset identifier
        asset_name: Display name of the asset
        asset_description: Description of the asset content
        asset_path: URL or file path to the asset
        asset_type: Type of asset (e.g. PDF, Text file, Image, Video, etc.)
        other_info: Additional metadata or notes
    """

    asset_id: Optional[str] = Field(default=None, description="Unique asset identifier")
    asset_name: Optional[str] = Field(default=None, description="Asset display name")
    asset_description: Optional[str] = Field(default=None, description="Asset description")
    asset_path: Optional[str] = Field(default=None, description="URL or file path")
    asset_type: Optional[str] = Field(default=None, description="Type of asset (e.g. PDF, Text file, Image, Video, etc.)")
    other_info: Optional[str] = Field(default=None, description="Additional info")

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )


# =============================================================================
# GUARDRAIL MODELS
# =============================================================================


class InputGuardrail(BaseModel):
    """
    Input guardrail validation result.

    Attributes:
        is_attack_query: Whether the query is detected as an attack
        reason: Explanation for the classification
        classification: Type of attack detected (if any)
    """

    is_attack_query: bool = Field(default=False, description="Attack detected flag")
    reason: Optional[str] = Field(default=None, description="Classification reason")
    classification: Optional[str] = Field(default=None, description="Attack type")
    response: str = Field(
        default="",
        description="User-facing response message. For attacks, a contextual deflection; for safe queries, empty.",
    )

    model_config = ConfigDict(validate_assignment=True)


class OutputGuardrail(BaseModel):
    """
    Output guardrail validation result.

    Attributes:
        validation_status_approved: Whether the output is approved
        issue: Description of any issues found
        original_text: Original text that was validated
        suggested_text: Corrected text suggestion
        reasoning: Explanation for the decision
    """

    validation_status_approved: Optional[str] = Field(
        default=None, description="Validation approval status"
    )
    issue: Optional[str] = Field(default=None, description="Issue description")
    original_text: Optional[str] = Field(default=None, description="Original text")
    suggested_text: Optional[str] = Field(
        default=None, description="Suggested correction"
    )
    reasoning: Optional[str] = Field(default=None, description="Decision reasoning")

    model_config = ConfigDict(validate_assignment=True)


# =============================================================================
# CONTACT & LEAD MODELS
# =============================================================================


class CollectedFields(BaseModel):
    """
    Fields collected during conversation.

    Attributes:
        name: User's full name
        email: User's email address
        phone: User's phone number
        date: Scheduled date
        time: Scheduled time
        products: List of products of interest
    """

    name: Optional[str] = Field(default=None, description="User's full name")
    email: Optional[str] = Field(default=None, description="User's email address")
    phone: Optional[str] = Field(default=None, description="User's phone number")
    date: Optional[str] = Field(default=None, description="Scheduled date")
    time: Optional[str] = Field(default=None, description="Scheduled time")
    products: Optional[List[str]] = Field(default=None, description="List of products of interest")

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )


class ContactDetails(BaseModel):
    """
    User contact information for booking workflows.

    Attributes:
        name: User's full name
        email: User's email address (critical for booking confirmation)
        phone: User's phone number
    """

    name: Optional[str] = Field(default=None, description="User's full name")
    email: Optional[str] = Field(default=None, description="User's email address")
    phone: Optional[str] = Field(default=None, description="User's phone number")

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    def get(self, key: str, default: Any = None) -> Any:
        """
        Safe dictionary-like access for backward compatibility.

        Args:
            key: Attribute name
            default: Value to return if attribute doesn't exist

        Returns:
            Attribute value or default
        """
        return getattr(self, key, default)


class Leads(BaseModel):
    """
    Lead information model.

    Attributes:
        name: Lead's full name
        email: Lead's email address
        phone: Lead's phone number
        products: List of products of interest
        date: Scheduled date
        time: Scheduled time
    """

    name: Optional[str] = Field(default=None, description="Lead's full name")
    email: Optional[str] = Field(default=None, description="Lead's email")
    phone: Optional[str] = Field(default=None, description="Lead's phone")
    products: Optional[List[str]] = Field(default=None, description="List of products of interest")
    date: Optional[str] = Field(default=None, description="Scheduled date")
    time: Optional[str] = Field(default=None, description="Scheduled time")

    model_config = ConfigDict(str_strip_whitespace=True)


class LeadAnalysis(BaseModel):
    """
    Lead analysis and classification results.

    Attributes:
        lead_classification: Classification (hot, warm, cold)
        reasoning: Analysis explanation
        key_indicators: Indicators that led to classification
        recommended_next_action: Suggested follow-up action
        urgency_level: How urgent the follow-up should be
    """

    lead_classification: Optional[str] = Field(
        default=None, description="Lead classification (hot/warm/cold)"
    )
    reasoning: Optional[str] = Field(default=None, description="Analysis reasoning")
    key_indicators: Optional[List[str]] = Field(
        default=None, description="Key classification indicators"
    )
    recommended_next_action: Optional[str] = Field(
        default=None, description="Recommended next action"
    )
    urgency_level: Optional[str] = Field(
        default=None, description="Urgency level (immediate/soon/later/no-interest)"
    )

    model_config = ConfigDict(validate_assignment=True)

    @field_validator("lead_classification")
    @classmethod
    def validate_classification(cls, v: Optional[str]) -> Optional[str]:
        """Validate lead classification value."""
        if v is not None:
            valid = [lc.value for lc in LeadClassification]
            if v.lower() not in valid:
                logger.warning(f"Invalid lead_classification: {v}")
        return v


# =============================================================================
# PROBING MODELS
# =============================================================================


class ProbingQuestion(BaseModel):
    """
    Individual probing question.

    Attributes:
        id: Unique question identifier
        question: The question text
        score: Score value for this question
        priority: Question priority order
        mandatory: Whether the question must be asked
    """

    id: str = Field(..., description="Unique question identifier")
    question: str = Field(..., description="Question text")
    score: float = Field(default=0.0, description="Score value")
    priority: Optional[int] = Field(default=None, description="Priority order")
    mandatory: Optional[bool] = Field(default=False, description="Mandatory flag")

    model_config = ConfigDict(str_strip_whitespace=True)


    @field_validator("score", mode="before")
    @classmethod
    def _sanitize_score(cls, v):
        return _safe_float(v)

class ProbingContext(BaseModel):
    """
    Context for probing question tracking.

    Attributes:
        detected_question_answer: List of answered questions with responses
        score_to_add: Accumulated score
        probing_completed: Whether probing is complete
        can_show_cta: Whether CTA can be shown
        is_objection: Whether current response is an objection
        detected_product_id: ID of Product mentioned during probing
    """

    detected_question_answer: List[Dict[str, Any]] = Field(
        default_factory=list, description="Answered questions with responses"
    )
    total_score: float = Field(default=0.0, description="Accumulated score")
    probing_completed: bool = Field(default=False, description="Probing complete flag")
    can_show_cta: bool = Field(default=False, description="CTA display flag")
    is_objection: bool = Field(default=False, description="Objection flag")
    detected_product_id: Optional[str] = Field(
        default=None, description="ID of Product detected during probing"
    )

    model_config = ConfigDict(validate_assignment=True)
    @field_validator("total_score", mode="before")
    @classmethod
    def _sanitize_total_score(cls, v):
        return _safe_float(v)

class EmailProbingPair(BaseModel):
    """
    Individual question-answer pair for email probing.

    In email mode, multiple probing questions can be sent in a single email
    (split using " + "). The user's reply may answer several questions at once.
    Each pair carries its own score so the total can be distributed.

    Attributes:
        question: The probing question text
        answer: The user's answer for this question
        score: Score assigned to this particular answer
        is_answered: Whether this specific question was answered
    """

    question: str = Field(default="", description="Probing question text")
    answer: str = Field(default="", description="User's answer for this question")
    score: float = Field(default=0.0, description="Score for this answer")
    is_answered: bool = Field(
        default=False, description="Whether this question was answered"
    )

    model_config = ConfigDict(validate_assignment=True)

    @field_validator("score", mode="before")
    @classmethod
    def _sanitize_score(cls, v):
        return _safe_float(v)


class ProbingOutput(BaseModel):
    """
    Output schema for probing agent.

    Attributes:
        detected_question: Which question was answered
        detected_answer: The answer provided by the user
        score_to_add: Score assigned to the answer
        probing_completed: Whether probing is complete
        can_show_cta: Whether CTA can be shown
        is_answered: Whether question was actually answered
        is_objection: Whether response is an objection
        reasoning: Explanation of the bot's thought process
        product_id: ID of product mentioned by user (if any)
        detected_question_answer_pairs: List of question-answer pairs for email
            probing. In email mode, multiple probing questions can be sent in a
            single email and the user may answer several at once. Each pair
            carries its own score so the total is distributed across them.
    """

    detected_question: str = Field(default="", description="Answered question")
    detected_answer: str = Field(default="", description="User's answer")
    score_to_add: float = Field(default=0.0, description="Score to add")
    probing_completed: bool = Field(default=False, description="Probing complete")
    can_show_cta: bool = Field(default=False, description="Show CTA flag")
    is_answered: bool = Field(default=False, description="Question answered flag")
    is_objection: bool = Field(default=False, description="Objection flag")
    reasoning: Optional[str] = Field(
        default=None, description="Bot's reasoning for this response"
    )
    product_id: Optional[str] = Field(
        default=None, description="ID of Product mentioned by user"
    )
    detected_question_answer_pairs: Optional[List[EmailProbingPair]] = Field(
        default=None,
        description=(
            "Multi-question probing pairs for email channel."
            "When set, each pair's score is summed to determine total_score."
            "Ignored for chatbot (MESSAGE) channel."
        ),
    )

    model_config = ConfigDict(validate_assignment=True)
    @field_validator("score_to_add", mode="before")
    @classmethod
    def _sanitize_score_to_add(cls, v):
        return _safe_float(v)


class ObjectionAnalysis(BaseModel):
    """
    Detailed analysis of a user objection.

    Attributes:
        type_of_objection: Classification (soft, hard, or hidden)
        objection_reasoning: Detailed reasoning for the classification
    """

    type_of_objection: Optional[Literal["soft", "hard", "hidden"]] = Field(
        default=None, description="Objection type classification"
    )
    objection_reasoning: Optional[str] = Field(
        default=None, description="Detailed reasoning for classification"
    )

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )


class ObjectionState(BaseModel):
    """
    State tracking for objection handling.

    Attributes:
        current_objection_count: Number of objections received
        is_objection_limit_reached: Whether limit has been reached
        limit_reach_count: Counter for how many times limit has been hit and reset
        objection_analysis: Detailed analysis of the current objection
    """

    current_objection_count: int = Field(default=0, description="Objection count")
    is_objection_limit_reached: bool = Field(
        default=False, description="Limit reached flag"
    )
    limit_reach_count: int = Field(
        default=0, description="Tracks how many times objection limit has been reached and reset. When >= 2, objection count won't increment"
    )
    objection_analysis: Optional[ObjectionAnalysis] = Field(
        default=None, description="Detailed analysis of the current objection"
    )

    model_config = ConfigDict(validate_assignment=True)


# =============================================================================
# FOLLOWUP & EMAIL MODELS
# =============================================================================


class FollowupDetails(BaseModel):
    """
    Follow-up scheduling details.

    Attributes:
        followup_flag: Whether follow-up is scheduled
        followup_time: Scheduled follow-up time
        followup_msg: Follow-up message
        timezone_confirmed: Whether timezone is confirmed
    """

    followup_flag: bool = Field(default=False, description="Follow-up scheduled flag")
    followup_time: Optional[str] = Field(default=None, description="Follow-up time")
    followup_msg: Optional[str] = Field(default=None, description="Follow-up message")
    timezone_confirmed: bool = Field(default=False, description="Timezone confirmed")

    model_config = ConfigDict(validate_assignment=True)


class EmailTemplate(BaseModel):
    """
    Email template structure.

    Attributes:
        id: Template identifier
        name: Template name
        subject: Email subject
        body: Email body content
    """

    id: Optional[str] = Field(default=None, description="Template ID")
    name: Optional[str] = Field(default=None, description="Template name")
    subject: Optional[str] = Field(default=None, description="Email subject")
    body: Optional[str] = Field(default=None, description="Email body")

    model_config = ConfigDict(extra="ignore")


class ProceedEmailDetails(BaseModel):
    """
    Details for proceeding with email communication.

    Attributes:
        switch_to_email: Flag to switch to email
        email_template_id: Selected template ID
        email_template_name: Selected template name
        get_email_flag: Flag to request email
        reply_body: Reply content
        email: User's email address
    """

    switch_to_email: bool = Field(default=False, description="Switch to email flag")
    email_template_id: Optional[str] = Field(default=None, description="Template ID")
    email_template_name: Optional[str] = Field(
        default=None, description="Template name"
    )
    get_email_flag: bool = Field(default=False, description="Get email flag")
    reply_body: Optional[str] = Field(default=None, description="Reply body")
    email: Optional[str] = Field(default=None, description="User's email")

    model_config = ConfigDict(validate_assignment=True)


class AssetSharedDetails(BaseModel):
    """
    Details of an asset shared with the user.

    Tracks which asset was shared during conversation.

    Attributes:
        asset_id: ID of the shared asset
        asset_name: Name of the shared asset
        asset_path: Path/URL of the shared asset
    """

    asset_id: Optional[str] = Field(default=None, description="Shared asset ID")
    asset_name: Optional[str] = Field(default=None, description="Shared asset name")
    asset_path: Optional[str] = Field(default=None, description="Shared asset path/URL")

    model_config = ConfigDict(validate_assignment=True)


# =============================================================================
# PRICING & NEGOTIATION MODELS
# =============================================================================
class NegotiationConfig(BaseModel):
    """
    Configuration for negotiation settings.
    
    Attributes:
        max_discount_percent: Maximum discount allowed
        currency: Currency symbol or code
    """
    max_discount_percent: float = Field(default=0.0, description="Maximum discount allowed")
    currency: str = Field(default="INR", description="Currency")
    model_config = ConfigDict(validate_assignment=True)

class NegotiatedProduct(BaseModel):
    """
    Details of a product that has been negotiated.

    Attributes:
        product_name: Name of the product being negotiated
        product_id: Id of the product being negotiated
        active_base_price: Base price of the product currently being negotiated
        max_discount_percent: Maximum discount percent allowed for this product (system-managed)
        current_discount_percent: Current discount offered
        final_price: Final locked price after negotiation is complete
        negotiation_attempts: Number of negotiation rounds for this product
        negotiation_phase: Current phase of negotiation (initial, active, closing)
        negotiation_active: Whether negotiation is currently active for this product
        discount_locked: Whether price is locked (no further negotiations)
        last_offer_response: User's response to the last offer made
        user_budget_constraint: User's stated budget constraint for this product
        negotiation_discount_offered: Whether a discount was offered in the last response
        internal_note: Internal strategy note for next negotiation round specific to this product
        reasoning: Reasoning of why this response is generated
    """
    ## Product Identity
    product_name: Optional[str] = Field(
        default=None, description="Product being negotiated"
    )
    product_id: Optional[str] = Field(
        default=None, description="Id of the Product"
    )
    plan_name: Optional[str] = Field(
        default=None, description="Plan being negotiated"
    )
    plan_id: Optional[str] = Field(
        default=None, description="Id of the Plan"
    )
    
    ## Pricing
    active_base_price: Optional[float] = Field(
        default=None, description="Base price of the product currently being negotiated"
    )
    max_discount_percent: Optional[float] = Field(
        default=0.0, description="Maximum discount percent allowed for this product (system-managed)"
    )
    current_discount_percent: float = Field(
        default=0.0, description="Current discount offered"
    )
    final_price: Optional[float] = Field(
        default=None, description="Final Locked Price Post-Negotiation discount is locked"
    )

    ## Round State
    negotiation_attempts: int = Field(
        default=0, description="Number of negotiation rounds for THIS product only"
    )
    negotiation_phase: Optional[str] = Field(
        default="initial", description="Phase: initial, active, or closing"
    )
    negotiation_active: bool = Field(
        default=False, description="Negotiation currently active"
    )
    discount_locked: bool = Field(
        default=False, description="Price locked flag - no further negotiations"
    )

    ## User Signals
    last_offer_response: Optional[str] = Field(
        default=None, description="User's response to last offer"
    )
    user_budget_constraint: Optional[float] = Field(
        default=None, description="User's stated budget limit"
    )
    negotiation_discount_offered: bool = Field(
        default=False, description="Whether a discount was offered in this response"
    )

    ## Strategy
    internal_note: Optional[str] = Field(
        default=None, description="Internal strategy note for next negotiation round Unique to each product"
    )
    reasoning: str = Field(..., description="Reasoning of why this response is generated")
    @field_validator(
        "active_base_price", "max_discount_percent", "current_discount_percent",
        "final_price", "user_budget_constraint", mode="before"
    )
    @classmethod
    def _sanitize_floats(cls, v):
        if v is None:
            return v
        return _safe_float(v)

class NegotiationAgentResponse(BaseModel):
    """
    Pricing and negotiation context for tracking negotiation state.

    Attributes:
        negotiated_products: List of products that have been negotiated in this session
        current_product_name: Name of the product currently being negotiated
        current_product_id: Id of the product currently being negotiated
        response: Response generated by the negotiation agent for the current round
    """
    negotiated_products: List[NegotiatedProduct] = Field(
        default_factory=list, description="List of negotiated products"
    )
    current_product_name: Optional[str] = Field(
        default=None, description="Product being negotiated"
    )
    current_product_id : Optional[str] = Field(
        default=None, description="Id of the Product being negotiated"
    )
    response : str = Field(description="Response from the negotiation engine")
    model_config = ConfigDict(validate_assignment=True)


class NegotiationState(BaseModel) :
    """
   Negotiation context for tracking negotiation state.

    Attributes:
        negotiation_config: Admin Configuration for Negotiation Engine
        internal_note: Internal strategy note for tracking between rounds
    """
    negotiation_config : Optional[NegotiationConfig] = Field(default_factory=NegotiationConfig, description="Admin Configuration for Negotiation Engine")
    internal_note: Optional[str] = Field(
        default=None, description="Internal strategy note for next negotiation round (not shown to user)"
    )
    negotiation_session : Optional[NegotiationAgentResponse] = Field(
        default=None, description="Negotiation session includes the fields populated by the Agent + Response"
    )

# =============================================================================
# BOOKING MODELS
# =============================================================================


class BookingFields(BaseModel):
    """
    Booking state management model.

    Tracks demo/meeting booking progress and ensures immutability
    of booking_type throughout the conversation.

    Attributes:
        booking_type: 'new', 'reschedule', or 'cancel' - IMMUTABLE once set
        booking_confirmed: True when calendly slot is available and confirmed
        ask_new_date: True when no alternatives available, need user suggestion
        calendly_checked: True when calendly availability was checked
    """

    booking_type: Optional[str] = Field(default=None, description="Booking type")
    booking_confirmed: bool = Field(default=False, description="Booking confirmed")
    ask_new_date: bool = Field(default=False, description="Ask for new date")
    calendly_checked: bool = Field(default=False, description="Calendly checked")

    model_config = ConfigDict(validate_assignment=True)


class HumanDetails(BaseModel):
    """
    Details for human escalation.

    Attributes:
        summary: Conversation summary
        key_topics: Main topics discussed
        user_sentiment: Detected user sentiment
        unresolved_issues: List of unresolved issues
        user_intent: Detected user intent
        email_validated: Whether email was validated
        email_suggestion: Suggested email correction
        email_typo_detected: Whether typo was detected
        escalation_reason: Reason for escalation
        priority: Escalation priority
        ready_for_handoff: Whether ready for human handoff
    """

    summary: Optional[str] = Field(default=None, description="Conversation summary")
    key_topics: Optional[List[str]] = Field(default=None, description="Key topics")
    user_sentiment: Optional[str] = Field(default=None, description="User sentiment")
    unresolved_issues: Optional[List[str]] = Field(
        default=None, description="Unresolved issues"
    )
    user_intent: Optional[str] = Field(default=None, description="User intent")
    email_validated: Optional[bool] = Field(default=False, description="Email validated")
    email_suggestion: Optional[str] = Field(
        default=None, description="Email suggestion"
    )
    email_typo_detected: Optional[bool] = Field(
        default=None, description="Typo detected"
    )
    escalation_reason: Optional[str] = Field(
        default=None, description="Escalation reason"
    )
    priority: Optional[str] = Field(default=None, description="Priority level")
    ready_for_handoff: Optional[bool] = Field(default=False, description="Ready for handoff")
    human_availability_checked: Optional[bool] = Field(
        default=False, description="Whether human availability has been checked"
    )
    human_preferred_time: Optional[str] = Field(
        default=None, description="User's preferred time for human callback"
    )
    human_slot_confirmed: Optional[bool] = Field(
        default=False, description="Whether a human agent slot has been confirmed"
    )
    human_slot_details: Optional[Dict[str, Any]] = Field(
        default=None, description="Confirmed human agent slot details"
    )
    human_availability_window: Optional[str] = Field(
        default=None, description="Time window communicated to user (e.g. 'within 30 minutes')"
    )

    model_config = ConfigDict(validate_assignment=True)


# =============================================================================
class WorkingHours(BaseModel):
    """Working hours configuration for a specific day"""

    day: str  # Monday, Tuesday, etc.
    type: Literal["Working", "Holiday"]
    start_time: Optional[str] = None  # HH:MM format
    end_time: Optional[str] = None  # HH:MM format


class Management(BaseModel):
    name: str
    designation: str
    email: Optional[str] = None
    phone_number: Optional[str] = None

class Holiday(BaseModel):
    name: str
    date: str  # YYYY-MM-DD format

# =============================================================================

# =============================================================================
# BOT PERSONA MODEL
# =============================================================================


class BotPersona(BaseModel):
    """
    Bot persona configuration model.

    Defines the bot's identity, company information, and behavior settings.
    This can be customized per tenant/deployment.

    Attributes:
        name: Bot's display name
        industry: Target industry
        category: Business category
        sub_category: Business sub-category
        business_type: Type of business (B2B, B2C, etc.)
        company_name: Company name
        company_domain: Company domain
        company_description: Company description
        company_products: List of products
        core_usps: Core unique selling points
        core_features: Core features
        contact_info: Contact information
        language: Primary language
        rules: Behavior rules
        offer_description: Current offer description
        prompt: Custom system prompt
        personality: Bot personality traits
        business_focus: Business focus area
        goal_type: Primary goal type
        use_emoji: Whether to use emojis
        use_name_reference: Whether to use user's name
        probing_questions: List of probing questions
        probing_threshold: Score threshold for probing completion
        enable_probing: Whether probing is enabled
        current_cta: Current call-to-action
        objection_count_limit: Maximum objections before stopping
        reset_count_limit: Limit for objection reset cycles
    """

    name: str = Field(default="", description="Bot's display name")
    industry: str = Field(default="", description="Target industry")
    category: str = Field(default="", description="Business category")
    sub_category: str = Field(default="", description="Business sub-category")
    business_type: str = Field(default="", description="Business type")
    company_name: str = Field(default="", description="Company name")
    company_domain: str = Field(default="", description="Company domain")
    company_description: str = Field(default="", description="Company description")
    company_products: List[Products] = Field(
        default_factory=list, description="Company products"
    )
    core_usps: str = Field(default="", description="Core USPs")
    core_features: str = Field(default="", description="Core features")
    contact_info: str = Field(default="", description="Contact info")
    language: Optional[str] = Field(default=None, description="Primary language")
    rules: Optional[List[str]] = Field(default=None, description="Behavior rules")
    offer_description: Optional[str] = Field(default=None, description="Current offer")
    prompt: Optional[str] = Field(default=None, description="Custom prompt")
    personality: Optional[str] = Field(default=None, description="Personality traits")
    business_focus: Optional[str] = Field(default=None, description="Business focus")
    goal_type: Optional[str] = Field(default=None, description="Goal type")
    use_emoji: bool = Field(default=False, description="Use emojis")
    use_name_reference: bool = Field(default=False, description="Use user's name")

    # Probing settings
    probing_questions: List[ProbingQuestion] = Field(
        default_factory=list, description="Probing questions"
    )
    probing_threshold: int = Field(
        default=DEFAULT_PROBING_THRESHOLD, description="Probing score threshold"
    )
    enable_probing: bool = Field(default=False, description="Enable probing")
    current_cta: Optional[str] = Field(default=None, description="Current CTA")
    objection_count_limit: int = Field(
        default=DEFAULT_OBJECTION_LIMIT, description="Objection limit"  # currently 3
    )
    reset_count_limit: int = Field(
        default=DEFAULT_RESET_COUNT_LIMIT, description="Limit for objection reset cycles"
    )
    holiday : Optional[List[Holiday]] = Field(default_factory=list, description="Holiday list")
    working_hours: Optional[List[WorkingHours]] = Field(
        default_factory=lambda: [
            WorkingHours(
                day="Monday", type="Working", start_time="10:00", end_time="19:00"
            ),
            WorkingHours(
                day="Tuesday", type="Working", start_time="10:00", end_time="19:00"
            ),
            WorkingHours(
                day="Wednesday", type="Working", start_time="10:00", end_time="19:00"
            ),
            WorkingHours(
                day="Thursday", type="Working", start_time="10:00", end_time="19:00"
            ),
            WorkingHours(
                day="Friday", type="Working", start_time="10:00", end_time="19:00"
            ),
            WorkingHours(
                day="Saturday", type="Holiday", start_time=None, end_time=None
            ),
            WorkingHours(day="Sunday", type="Holiday", start_time=None, end_time=None),
        ]
    )
    company_management: Optional[List[Management]] = None
    negotiation_config: Optional[NegotiationConfig] = Field(
        default_factory=lambda: NegotiationConfig(
            max_discount_percent=0.0, currency="INR"
        ),
        description="Negotiation configuration",
    )

    # Asset sharing settings
    assets: Optional[List[Asset]] = Field(
        default_factory=list, description="Shareable assets (brochures, PDFs, documents)"
    )
    email_template: Optional[List[EmailTemplate]] = Field(
        default=None, description="Available templates"
    )

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )


# =============================================================================
# USER CONTEXT MODEL
# =============================================================================


class UserContext(BaseModel):
    """
    User session context model.

    Contains all information about the current user session including
    conversation history, collected fields, and session state.

    Attributes:
        user_id: Unique user identifier
        message_id: Unique message identifier
        user_query: Current user query
        tenant_id: Tenant identifier
        chat_summary: Summarized conversation
        executive_summary: Executive summary
        chat_history: Full chat history
        to_summarise: Flag for summarization
        retrieved_docs: Retrieved documents
        contact_details: User contact details
        lead_details: Lead analysis results
        follow_trigger: Follow-up trigger flag
        ask_new_date: Ask new date flag
        previous_time: Previous scheduled time
        previous_date: Previous scheduled date
        timezone: User timezone
        region_code: User region code
        ismultiple_timezone: Multiple timezone flag
        collected_fields: All collected fields
        all_info_collected: All info collected flag
        booking_confirmed: Booking confirmed flag
        booking_type: Booking type
        new_booking: New booking flag
        cache_pairs: Cached Q&A pairs
        last_agent: Last agent that handled query
        agent_result: Agent execution result
        reply_body: Reply content
        human_requested: Human escalation flag
        escalation_reason: Reason for escalation
        escalation_timestamp: When escalation occurred
        followup_details: Follow-up details
        probing_details: Probing details
    """

    user_id: Optional[str] = Field(default=None, description="User ID")
    message_id: str = Field(
        default_factory=lambda: str(_uuid.uuid4()),
        description="Unique ID for this message/turn — use to correlate all logs for a single request",
    )
    user_query: str = Field(default="", description="Current query")
    tenant_id: str = Field(default="", description="Tenant ID")
    chat_summary: str = Field(default="", description="Chat summary")
    executive_summary: str = Field(default="", description="Executive summary")
    chat_history: List[Dict[str, Any]] = Field(
        default_factory=list, description="Chat history"
    )
    to_summarise: bool = Field(default=False, description="Summarize flag")
    retrieved_docs: List[str] = Field(
        default_factory=list, description="Retrieved docs"
    )
    contact_details: Optional[ContactDetails] = Field(
        default=None, description="Contact details"
    )
    lead_details: Optional[LeadAnalysis] = Field(
        default=None, description="Lead details"
    )
    follow_trigger: bool = Field(default=False, description="Follow-up trigger")
    ask_new_date: bool = Field(default=False, description="Ask new date")
    previous_time: Optional[str] = Field(default=None, description="Previous time")
    previous_date: Optional[str] = Field(default=None, description="Previous date")
    timezone: Optional[str] = Field(default=None, description="Timezone")
    region_code: Optional[str] = Field(default=None, description="Region code")
    ismultiple_timezone: bool = Field(default=False, description="Multiple timezones")
    collected_fields: Optional[Dict[str, Any]] = Field(
        default=None, description="Collected fields"
    )
    all_info_collected: bool = Field(default=False, description="All info collected")
    booking_confirmed: bool = Field(default=False, description="Booking confirmed")
    booking_type: Optional[str] = Field(default=None, description="Booking type")
    new_booking: bool = Field(default=False, description="New booking")
    cache_pairs: Optional[List[Dict[str, Any]]] = Field(
        default=None, description="Cache pairs from semantic search"
    )
    last_agent: Optional[str] = Field(default=None, description="Last agent")
    agent_result: List[Dict[str, Any]] = Field(
        default_factory=list, description="Agent result"
    )
    human_requested: bool = Field(default=False, description="Human requested")
    escalation_reason: Optional[str] = Field(
        default=None, description="Escalation reason"
    )
    escalation_timestamp: Optional[str] = Field(
        default=None, description="Escalation timestamp"
    )
    followup_details: Optional[FollowupDetails] = Field(
        default=None, description="Followup details"
    )
    probing_details: Optional[ProbingOutput] = Field(
        default=None, description="Probing details"
    )
    objection_analysis: Optional[ObjectionAnalysis] = Field(
        default=None, description="Detailed analysis of user objection"
    )
    human_details: Optional[HumanDetails] = Field(
        default=None, description="Human escalation handoff details"
    )
    user_language: Optional[str] = Field(default=None, description="Detected user language (set once by main agent)")
    user_script: Optional[str] = Field(default=None, description="Detected user script (set once by main agent)")
    url_sent: bool = Field(default=False, description="Whether a URL was sent in the response")
    plan_id: Optional[str] = Field(default=None, description="Plan ID associated with the sent URL")
    model_config = ConfigDict(
        validate_assignment=True,
        arbitrary_types_allowed=True,
    )


# =============================================================================
# CONSUMPTION TRACKING MODELS
# =============================================================================


class LLMResponseDetail(BaseModel):
    """
    Per-LLM-call detail within a single user request.

    Captures token usage and model identity for each individual
    LLM call made during a request.

    Attributes:
        response_index: Sequential index of the response in the request
        model_name: LLM model that served this response (e.g. "gpt-4.1")
        input_tokens: Number of input/prompt tokens
        output_tokens: Number of output/completion tokens
        cached_tokens: Number of cached input tokens (prompt caching)
        total_tokens: Total tokens (input + output)
    """

    response_index: int = Field(default=0, description="Sequential index of the response")
    model_name: Optional[str] = Field(default=None, description="LLM model name")
    stage_name: Optional[str] = Field(default=None, description="Name of the stage or agent (e.g. input_guardrail, main_agent)")
    input_tokens: int = Field(default=0, description="Input/prompt tokens")
    output_tokens: int = Field(default=0, description="Output/completion tokens")
    cached_tokens: int = Field(default=0, description="Cached input tokens")
    total_tokens: int = Field(default=0, description="Total tokens")

    model_config = ConfigDict(validate_assignment=True)


class ConsumptionInfo(BaseModel):
    """
    Rich consumption metadata for a single user request.

    Tracks everything about LLM resource consumption: which model
    was used, which agent handled the request, token breakdowns,
    and operational metadata.

    Attributes:
        request_timestamp: ISO-8601 UTC timestamp of when the request was processed
        agent_name: Last agent that handled the request (e.g. sales_agent)
        primary_model: Configured primary model name from settings
        tags: Operational tags (e.g. ["sales", "probing"])
        responses: Per-LLM-call token details
        totals: Aggregated token usage across all LLM calls
    """

    request_timestamp: Optional[str] = Field(
        default=None, description="ISO-8601 UTC timestamp of request processing"
    )
    agent_name: Optional[str] = Field(
        default=None, description="Last agent that handled the request"
    )
    primary_model: Optional[str] = Field(
        default=None, description="Configured primary model name from settings"
    )
    tags: Optional[List[str]] = Field(
        default=None, description="Operational tags (e.g. ['sales', 'probing'])"
    )
    responses: List[LLMResponseDetail] = Field(
        default_factory=list, description="Per-LLM-call token details"
    )
    individual_consumption: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict, description="Detailed breakdown per stage/agent"
    )
    totals: Dict[str, int] = Field(
        default_factory=lambda: {
            "input_tokens": 0,
            "output_tokens": 0,
            "cached_tokens": 0,
            "total_tokens": 0,
        },
        description="Aggregated token usage across all LLM calls",
    )

    model_config = ConfigDict(validate_assignment=True)


# =============================================================================
# RESPONSE FORMATTER OUTPUT MODEL
# =============================================================================


class ResponseFormatterOutput(BaseModel):
    """
    Output model for the Response Formatter agent.

    Attributes:
        is_spam: Whether the email response was classified as spam
        reasoning: Short explanation if spam, empty string otherwise
        final_response: Original body if not spam, rewritten body if spam
    """

    is_spam: bool = Field(default=False, description="True if email classified as spam")
    reasoning: str = Field(default="", description="Short spam reasoning or empty")
    final_response: str = Field(
        default="", description="Final email body (original or rewritten)"
    )

    model_config = ConfigDict(validate_assignment=True)


# =============================================================================
# BOT STATE MODEL
# =============================================================================


class BotState(BaseModel):
    """
    Main bot state model.

    Contains the complete state of a bot conversation including
    user context, persona, and execution state.

    Attributes:
        user_context: User session context
        bot_persona: Bot persona configuration
        session_id: Session identifier
        conversation_id: Conversation identifier
        input_guardrail_decision: Input guardrail result
        response: Bot response text
        probing_context: Probing state
        objection_state: Objection tracking state
        pricing_context: Pricing negotiation state
    """

    user_context: UserContext = Field(
        default_factory=UserContext, description="User context"
    )
    bot_persona: Optional[BotPersona] = Field(default=None, description="Bot persona")
    session_id: Optional[str] = Field(default=None, description="Session ID")
    conversation_id: Optional[str] = Field(default=None, description="Conversation ID")
    input_guardrail_decision: Optional[InputGuardrail] = Field(
        default=None, description="Input guardrail decision"
    )
    response: Optional[str] = Field(default=None, description="Bot response")
    probing_context: ProbingContext = Field(
        default_factory=ProbingContext, description="Probing context"
    )
    objection_state: ObjectionState = Field(
        default_factory=ObjectionState, description="Objection state"
    )
    negotiation_state: NegotiationState = Field(
        default_factory=NegotiationState, description="Negotiation State (contains response from negotiation agent as well)"
    )

    # Temporary storage for additional raw responses (e.g. from guardrails or tools)
    additional_raw_responses: List[Any] = Field(default_factory=list)

    # Brochure / Asset sharing flags
    brochure_flag: bool = Field(default=False, description="Whether a brochure/asset was shared in this session")
    brochure_details: Optional[AssetSharedDetails] = Field(
        default=None, description="Details of the shared brochure/asset (asset_id, asset_name, asset_path)"
    )
    consumption_info: Optional[ConsumptionInfo] = Field(
        default=None, description="Rich consumption metadata per request (model, agent, tokens, tags)"
    )
    model_config = ConfigDict(
        validate_assignment=True,
        arbitrary_types_allowed=True,
    )

    @field_validator("bot_persona", mode="before")
    @classmethod
    def ensure_bot_persona(cls, v):
        """Ensure bot_persona is never None - create default if needed."""
        if v is None:
            return BotPersona()
        return v

    def update_response(self, response: str) -> "BotState":
        """
        Update the response field and return updated state.

        Args:
            response: New response text

        Returns:
            Updated BotState instance
        """
        self.response = response
        return self

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert state to dictionary for serialization.

        Returns:
            Dictionary representation of state
        """
        return self.model_dump(exclude_none=True)


# =============================================================================
# BOT RESPONSE MODEL
# =============================================================================


class BotResponse(BaseModel):
    """
    Bot response output model.

    Used as the structured output type for agent responses.
    Contains all fields that may be returned by an agent.
    
    IMPORTANT: probing_details and reasoning are placed BEFORE response
    so that OpenAI structured output generates the score computation
    and CTA decision BEFORE writing the response text.
    
    Attributes:
        probing_details: Probing details (generated first for CTA decision)
        reasoning: Internal reasoning (generated before response)
        response: Response text (generated after all computation)
        booking_confirmed: Booking confirmed flag
        lead_details: Lead information
        contact_details: Contact information
        timezone: User timezone
        region_code: User region
        ismultiple_timezone: Multiple timezone flag
        previous_time: Previous scheduled time
        previous_date: Previous scheduled date
        collected_fields: Collected information
        all_info_collected: All info collected flag
        new_booking: New booking flag
        followup_details: Follow-up details
        output_guardrail: Output guardrail result
        output_guardrail_decision: Output guardrail decision
        booking_fields: Booking fields
    """
    probing_details: Optional[ProbingOutput] = Field(
        default_factory=ProbingOutput,
        description="Probing details — score computation and CTA decision"
    )

    objection_analysis: Optional[ObjectionAnalysis] = Field(
        default=None, description="Detailed analysis of user objection"
    )
    user_language: Optional[str] = Field(default=None, description="Detected user language (set once by main agent)")
    user_script: Optional[str] = Field(default=None, description="Detected user script (set once by main agent)")
    reasoning: Optional[str] = Field(default=None, description="Internal reasoning behind the response")
    response: Optional[str] = Field(default="", description="Response text")
    
    @field_validator('response', mode='before')
    @classmethod
    def ensure_response_string(cls, v):
        """Ensure response is never None, convert to string, and sanitize markdown/dashes."""
        from emailbot.utils.utils import sanitize_response
        
        if v is None:
            return ""
        
        # Convert to string
        text = str(v)
        
        # Sanitize the response text
        text = sanitize_response(text)
        
        return text

    booking_confirmed: bool = Field(default=False, description="Booking confirmed")
    lead_details: Optional[Leads] = Field(default=None, description="Lead details")
    contact_details: Optional[ContactDetails] = Field(
        default=None, description="Contact details"
    )
    timezone: Optional[str] = Field(default=None, description="Timezone")
    region_code: Optional[str] = Field(default=None, description="Region code")
    ismultiple_timezone: bool = Field(default=False, description="Multiple timezones")
    previous_time: Optional[str] = Field(default=None, description="Previous time")
    previous_date: Optional[str] = Field(default=None, description="Previous date")
    collected_fields: Optional[CollectedFields] = Field(
        default=None, description="Collected fields"
    )
    all_info_collected: bool = Field(default=False, description="All info collected")
    new_booking: bool = Field(default=False, description="New booking")
    followup_details: Optional[FollowupDetails] = Field(
        default=None, description="Followup details"
    )
    proceed_email_details: Optional[ProceedEmailDetails] = Field(
        default=None, description="Email details"
    )
    output_guardrail: Optional[OutputGuardrail] = Field(
        default=None, description="Output guardrail"
    )
    output_guardrail_decision: Optional[OutputGuardrail] = Field(
        default=None, description="Guardrail decision"
    )
    booking_fields: Optional[BookingFields] = Field(
        default=None, description="Booking fields"
    )
    negotiation_details: Optional[NegotiationAgentResponse] = Field(
        default=None, description="Updated pricing negotiation state with discount tracking and strategy notes"
    )
    human_details: Optional[HumanDetails] = Field(
        default=None, description="Human escalation handoff details"
    )
    brochure_details: Optional[AssetSharedDetails] = Field(
        default=None, description="Asset sharing details (brochure/document shared)"
    )
    url_sent: bool = Field(default=False, description="Whether a URL was sent in the response")
    plan_id: Optional[str] = Field(default=None, description="Plan ID associated with the sent URL")

    model_config = ConfigDict(validate_assignment=True)



# =============================================================================
# API REQUEST/RESPONSE MODELS
# =============================================================================


class UserContextRequest(BaseModel):
    """
    User context in API request format.

    Pydantic model for API request validation.
    """

    user_id: Optional[str] = Field(default=None, description="User ID")
    message_id: Optional[str] = Field(
        default=None,
        description="Unique ID for this message/turn — forwarded from client or auto-generated at start of run",
    )
    user_query: str = Field(default="", description="User query")
    user_email_id: Optional[str] = Field(default=None, description="User's email ID")
    tenant_id: str = Field(default="", description="Tenant ID")
    chat_history: Optional[List[Dict[str, Any]]] = Field(
        default=None, description="Chat history"
    )
    contact_details: Optional[ContactDetails] = Field(
        default=None, description="Contact details"
    )
    timezone: Optional[str] = Field(default=None, description="Timezone")
    region_code: Optional[str] = Field(default=None, description="Region code")
    model_config = ConfigDict(str_strip_whitespace=True)


class BotRequest(BaseModel):
    """
    API request model for chat endpoint.

    Attributes:
        user_context: User context information
        bot_persona: Optional persona override
    """

    user_context: UserContextRequest = Field(..., description="User context")
    bot_persona: Optional[BotPersona] = Field(default=None, description="Bot persona")

    model_config = ConfigDict(str_strip_whitespace=True)


class APIResponse(BaseModel):
    """
    API response model for chat endpoint.

    Attributes:
        response: Bot response text
        user_id: User identifier
        tenant_id: Tenant identifier
        chat_history: Updated chat history
        chat_summary: Conversation summary
        executive_summary: Executive summary
    """

    response: str = Field(default="", description="Response text")
    user_id: Optional[str] = Field(default=None, description="User ID")
    message_id: str = Field(
        default_factory=lambda: str(_uuid.uuid4()),
        description="Unique ID for this message/turn — use to correlate all logs for a single request",
    )
    tenant_id: Optional[str] = Field(default=None, description="Tenant ID")
    chat_history: Optional[List[Dict[str, Any]]] = Field(
        default=None, description="Chat history"
    )
    chat_summary: Optional[str] = Field(default=None, description="Chat summary")
    executive_summary: Optional[str] = Field(
        default=None, description="Executive summary"
    )
    contact_details: Optional[ContactDetails] = Field(
        default=None, description="Contact details"
    )
    lead_details: Optional[LeadAnalysis] = Field(
        default=None, description="Lead details"
    )
    follow_trigger: bool = Field(default=False, description="Follow-up trigger")
    ask_new_date: bool = Field(default=False, description="Ask new date")
    timezone: Optional[str] = Field(default=None, description="Timezone")
    region_code: Optional[str] = Field(default=None, description="Region code")
    collected_fields: Optional[Dict[str, Any]] = Field(
        default=None, description="Collected fields"
    )
    all_info_collected: bool = Field(default=False, description="All info collected")
    booking_confirmed: bool = Field(default=False, description="Booking confirmed")
    booking_type: Optional[str] = Field(default=None, description="Booking type")
    new_booking: bool = Field(default=False, description="New booking")
    last_agent: Optional[str] = Field(default=None, description="Last agent")
    followup_details: Optional[FollowupDetails] = Field(
        default=None, description="Followup details"
    )
    probing_details: Optional[ProbingOutput] = Field(
        default=None, description="Probing details"
    )
    objection_analysis: Optional[ObjectionAnalysis] = Field(
        default=None, description="Detailed analysis of user objection"
    )
    human_details: Optional[HumanDetails] = Field(
        default=None, description="Human escalation handoff details"
    )
    human_requested: bool = Field(default=False, description="Human requested")
    escalation_reason: Optional[str] = Field(
        default=None, description="Escalation reason"
    )
    escalation_timestamp: Optional[str] = Field(
        default=None, description="Escalation timestamp"
    )
    consumption_info: Optional[ConsumptionInfo] = Field(
        default=None, description="LLM token consumption details"
    )
    brochure_flag: bool = Field(default=False, description="Whether a brochure/asset was shared this turn")
    asset_shared_details: Optional[AssetSharedDetails] = Field(
        default=None, description="Details of the asset shared (asset_id, asset_name, asset_path)"
    )


    model_config = ConfigDict(str_strip_whitespace=True)

# =============================================================================
# ACTIVITY SUMMARY MODEL    
# =============================================================================

class ActivityItem(BaseModel):
    """
    Activity item model.
    """
    title: Optional[str] = Field(default=None, description="Activity title")
    description: Optional[str] = Field(default=None, description="Activity description")
    contact_source: Optional[str] = Field(default=None, description="Contact source (Whatsapp/email/call/appointment)")
    stage: Optional[str] = Field(default=None, description="Stage (lead/opportunity/quotation/order/invoice)")

class AllSummary(BaseModel):
    """
    All summary model.

    Attributes:
        current_summary: Old summary
        activity: List of activities
    """
    current_summary: Optional[str] = Field(default=None, description="Current/old summary")
    activity: List[ActivityItem] = Field(default_factory=list, description="List of activities to consolidate")

class ActivitySummary(BaseModel):
    """
    Response model for activity summary.
    """
    activity_summary: Optional[str] = Field(default=None, description="Activity summary")
    consumption_info: Optional[ConsumptionInfo] = Field(default=None, description="LLM token consumption details")


# =============================================================================
# PROBING AGENT MODELS
# =============================================================================


class ProbingAgentRequest(BaseModel):
    """
    Request model for probing agent.

    Attributes:
        bot_persona: Bot persona for context
        total_k: Number of questions to generate
        existing_questions: Existing questions to consider
        comment: Additional comments/instructions
    """

    bot_persona: BotPersona = Field(..., description="Bot persona")
    total_k: int = Field(default=5, description="Questions to generate")
    existing_questions: List[ProbingQuestion] = Field(
        default_factory=list, description="Existing questions"
    )
    comment: Optional[str] = Field(default=None, description="Additional comments")

    model_config = ConfigDict(validate_assignment=True)


class ProbingAgentResponse(BaseModel):
    """
    Response model for probing agent.

    Attributes:
        questions: Generated probing questions
        total_k_generated: Number of questions generated
    """

    questions: List[ProbingQuestion] = Field(
        default_factory=list, description="Generated questions"
    )
    total_k_generated: int = Field(default=0, description="Questions generated count")
    consumption_info: Optional[ConsumptionInfo] = Field(default=None, description="LLM token consumption details")

    model_config = ConfigDict(validate_assignment=True)


class ProbingRequest(BaseModel):
    custom_persona: Optional[Dict] = None
    total_k: int = 5
    comment: str = ""
    tenant_id: Optional[str] = None


class InstructionAgentRequest(BaseModel):
    """Request model for instruction agent endpoint."""

    custom_persona: Optional[Dict] = Field(
        default=None, description="Bot persona for context"
    )
    max_instructions: int = Field(
        default=5, ge=1, le=10, description="Maximum number of instructions to generate"
    )

    model_config = ConfigDict(validate_assignment=True)


class InstructionAgentResponse(BaseModel):
    """Response model for instruction agent."""

    instructions: List[str] = Field(
        default_factory=list, description="Generated instructions"
    )
    consumption_info: Optional[ConsumptionInfo] = Field(default=None, description="LLM token consumption details")


class AutofillPersonaRequest(BaseModel):
    """Request model for autofill persona endpoint."""

    user_id: str = Field(..., description="User ID for Knowledge Base ingestion")
    url: str = Field(..., description="Website URL to crawl")
    tenant_id: Optional[str] = Field(default=None, description="Tenant ID for VectorDB")
    max_depth: int = Field(default=2, ge=1, le=5, description="Maximum crawl depth")
    max_pages: int = Field(
        default=50, ge=10, le=100, description="Maximum pages to crawl"
    )
    max_tokens: int = Field(
        default=30000, ge=10000, le=50000, description="Maximum tokens for LLM"
    )
    max_products: int = Field(
        default=5, ge=1, le=100, description="Maximum products to crawl"
    )

    model_config = ConfigDict(validate_assignment=True)


class AutofillPersonaResponse(BaseModel):
    """Response model for autofill persona endpoint."""
    pages_analyzed: int = Field(default=0, description="Number of pages analyzed")
    urls: List[str] = Field(default_factory=list, description="List of crawled URLs")
    bot_persona: Optional[Dict[str, Any]] = Field(default=None, description="Generated bot persona")
    consumption_info: Optional[ConsumptionInfo] = Field(default=None, description="LLM token consumption details")

    model_config = ConfigDict(validate_assignment=True)


class TemplateGenerationRequest(BaseModel):
    """Request model for generate_template endpoint"""

    custom_persona: Optional[Dict] = Field(
        default=None, description="Bot persona for context"
    )
    max_products: int = Field(
        default=5, ge=1, le=20, description="Maximum products to generate templates for"
    )


class TemplateButton(BaseModel):
    button_type: str = Field(
        default="Url",
        description="Button Type (one of these 3): Url, Quick Reply, Phone Number",
    )
    button_text: str = Field(
        default="",
        description="Content to be shown in button. Default is URL : URL of the website",
    )


class WhatsAppTemplate(BaseModel):
    ### Template Details
    name: str = Field(..., description="Name of the Template")
    category: str = Field(default="Utility", description="Marketing / Utility")
    language: str = Field(default="English", description="Language of the template")
    header_type: str = Field(default="Text", description="Text/Image/Video/Document")

    ### Message Content
    body: str = Field(
        ...,
        description="This is the body of the Message which will be sent to the User",
    )
    variables: Optional[List[str]] = Field(
        default=None,
        description="Variables for the Body, e.g. Variable {{1}} = 'Customer Name', ... etc. There can be multiple variables",
    )
    footer: Optional[str] = Field(default="To OPT Out, type STOP")

    ### Buttons
    buttons: Optional[List[TemplateButton]] = Field(
        default=None, description="List of Buttons"
    )


class TemplateGenerationResponse(BaseModel):
    templates: List[WhatsAppTemplate] = Field(default_factory=list)
    total_templates: int = Field(
        default=0, description="Total Number of Templates generated"
    )
    consumption_info: Optional[ConsumptionInfo] = Field(default=None, description="LLM token consumption details")

class HandoffArgs(BaseModel):
    user_language: Optional[str] = Field(default="English", description="Detected user language (set once by main agent)")
    user_script: Optional[str] = Field(default="Roman transliteration", description="Detected user script (set once by main agent)")


class ExecutiveSummaryRequest(BaseModel):
    """
    Request model for the standalone executive summary endpoint.

    Attributes:
        agent_result: Raw agent execution result (primary input).
        chat_history: Optional fallback chat history if agent_result is empty.
    """
    agent_result: List[Dict[str, Any]] = Field(
        default_factory=list, description="Raw agent execution result"
    )
    chat_history: Optional[List[Dict[str, Any]]] = Field(
        default=None, description="Optional chat history fallback"
    )

    model_config = ConfigDict(str_strip_whitespace=True)

class ExecutiveSummaryResponse(BaseModel):
    """
    Response model for executive summary endpoint.
    """
    executive_summary: Optional[str] = Field(default=None, description="Executive summary")
    consumption_info: Optional[ConsumptionInfo] = Field(
        default=None, description="LLM token consumption details"
    )


# =============================================================================
# BACKWARD COMPATIBILITY EXPORTS
# =============================================================================

# These ensure imports from the old state.py location still work
__all__ = [
    # Products
    "Products",
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
    "ObjectionAnalysis",
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
    "ProbingRequest",
    # Autofill
    "AutofillPersonaRequest",
    "AutofillPersonaResponse",
    # Instruction Agent
    "InstructionAgentRequest",
    "InstructionAgentResponse",
    #Negotiation Agent
    "NegotiationState",
    "NegotiationAgentResponse",
    "NegotiationConfig",    
    # Executive Summary
    "ExecutiveSummaryRequest",
    "ExecutiveSummaryResponse",
    # Consumption Tracking
    "LLMResponseDetail",
    "ConsumptionInfo",
    # Handoff Arguments
    "HandoffArgs",
    # Activity summary
    "ActivitySummary",
    "AllSummary",
]
