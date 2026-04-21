"""
Instruction Generators - Dynamic instruction generation for emailagents.

This module provides builders and utilities for generating dynamic
instructions (prompts) based on conversation state and context.

The InstructionBuilder pattern allows:
- Template-based prompt construction
- State-aware prompt customization
- Consistent formatting across emailagents
- Runtime instruction modification

Usage:
    from emailbot.instructions.generators import InstructionBuilder
    
    builder = InstructionBuilder(state)
    prompt = builder.build_main_instructions()
"""

from typing import Any, Dict, List, Optional, Callable
from abc import ABC, abstractmethod



from emailbot.config.settings import logger

from emailbot.core.models import BotState, BotPersona, UserContext


# =============================================================================
# BASE INSTRUCTION BUILDER
# =============================================================================


class BaseInstructionBuilder(ABC):
    """
    Abstract base class for instruction builders.

    Instruction builders generate dynamic prompts based on
    conversation state and persona configuration.
    """

    @abstractmethod
    def build(self) -> str:
        """
        Build and return the instruction string.

        Returns:
            Formatted instruction string
        """
        pass


class InstructionBuilder:
    """
    Builder for creating dynamic agent instructions.

    The InstructionBuilder uses the conversation state and bot persona
    to generate context-aware prompts for different emailagents.

    Attributes:
        state: Current bot state
        persona: Bot persona configuration
        context: User context
    """

    def __init__(self, state: BotState):
        """
        Initialize instruction builder with state.

        Args:
            state: Current BotState
        """
        self.state = state
        self.persona = state.bot_persona
        self.context = state.user_context

    def build_main_instructions(self) -> str:
        """
        Build instructions for the main agent.

        Returns:
            Formatted main agent prompt
        """
        from emailbot.prompts import main_prompt

        return main_prompt(self.state)

    def build_sales_instructions(self) -> str:
        """
        Build instructions for the sales agent.

        Returns:
            Formatted sales agent prompt
        """
        from emailbot.prompts import sales_prompt

        return sales_prompt(self.state)

    def build_followup_instructions(self) -> str:
        """
        Build instructions for the followup agent.

        Returns:
            Formatted followup prompt
        """
        from emailbot.prompts import followup_prompt

        return followup_prompt(self.state)

    def build_human_instructions(self) -> str:
        """
        Build instructions for the human escalation agent.

        Returns:
            Formatted human escalation prompt
        """
        from emailbot.prompts import human_agent_prompt

        return human_agent_prompt(self.state)



# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================


def build_main_instructions(state: BotState) -> str:
    """
    Build instructions for the main agent.

    Args:
        state: Current BotState

    Returns:
        Formatted main agent prompt
    """
    return InstructionBuilder(state).build_main_instructions()


def build_sales_instructions(state: BotState) -> str:
    """
    Build instructions for the sales agent.

    Args:
        state: Current BotState

    Returns:
        Formatted sales agent prompt
    """
    return InstructionBuilder(state).build_sales_instructions()



def build_followup_instructions(state: BotState) -> str:
    """
    Build instructions for the followup agent.

    Args:
        state: Current BotState

    Returns:
        Formatted followup prompt
    """
    return InstructionBuilder(state).build_followup_instructions()


def build_human_instructions(state: BotState) -> str:
    """
    Build instructions for the human escalation agent.

    Args:
        state: Current BotState

    Returns:
        Formatted human escalation prompt
    """
    return InstructionBuilder(state).build_human_instructions()


# =============================================================================
# TEMPLATE UTILITIES
# =============================================================================


class PromptTemplate:
    """
    Template for generating prompts with variable substitution.

    Attributes:
        template: The template string with {variable} placeholders
        required_vars: List of required variable names
    """

    def __init__(self, template: str, required_vars: Optional[List[str]] = None):
        """
        Initialize prompt template.

        Args:
            template: Template string with {variable} placeholders
            required_vars: Optional list of required variables
        """
        self.template = template
        self.required_vars = required_vars or []

    def render(self, **kwargs) -> str:
        """
        Render the template with provided variables.

        Args:
            **kwargs: Variable values for substitution

        Returns:
            Rendered prompt string

        Raises:
            ValueError: If required variables are missing
        """
        # Check required variables
        missing = [v for v in self.required_vars if v not in kwargs]
        if missing:
            raise ValueError(f"Missing required variables: {missing}")

        # Render template
        try:
            return self.template.format(**kwargs)
        except KeyError as e:
            logger.error(f"Template variable not found: {e}")
            raise


class CompositePromptBuilder:
    """
    Builder for composing prompts from multiple sections.

    Allows building complex prompts by combining multiple
    template sections with separators.
    """

    def __init__(self, separator: str = "\n\n"):
        """
        Initialize composite prompt builder.

        Args:
            separator: String to use between sections
        """
        self.sections: List[str] = []
        self.separator = separator

    def add_section(self, section: str) -> "CompositePromptBuilder":
        """
        Add a section to the prompt.

        Args:
            section: Section content to add

        Returns:
            Self for method chaining
        """
        if section.strip():
            self.sections.append(section.strip())
        return self

    def add_template(
        self, template: PromptTemplate, **kwargs
    ) -> "CompositePromptBuilder":
        """
        Add a rendered template section.

        Args:
            template: PromptTemplate to render
            **kwargs: Variables for template rendering

        Returns:
            Self for method chaining
        """
        rendered = template.render(**kwargs)
        return self.add_section(rendered)

    def add_conditional(
        self, condition: bool, section: str
    ) -> "CompositePromptBuilder":
        """
        Add a section only if condition is true.

        Args:
            condition: Whether to add the section
            section: Section content to add

        Returns:
            Self for method chaining
        """
        if condition:
            return self.add_section(section)
        return self

    def build(self) -> str:
        """
        Build the final prompt string.

        Returns:
            Composed prompt string
        """
        return self.separator.join(self.sections)

    def clear(self) -> "CompositePromptBuilder":
        """
        Clear all sections.

        Returns:
            Self for method chaining
        """
        self.sections.clear()
        return self


# =============================================================================
# CONTEXT FORMATTERS
# =============================================================================


def format_chat_history(history: List[Dict[str, Any]], max_messages: int = 10) -> str:
    """
    Format chat history for inclusion in prompts.

    Args:
        history: List of chat messages
        max_messages: Maximum messages to include

    Returns:
        Formatted history string
    """
    if not history:
        return "No previous conversation."

    # Take last N messages
    recent = history[-max_messages:]

    formatted = []
    for msg in recent:
        role = msg.get("role", "unknown").capitalize()
        content = msg.get("content", "")
        formatted.append(f"{role}: {content}")

    return "\n".join(formatted)


def format_collected_fields(fields: Optional[Dict[str, Any]]) -> str:
    """
    Format collected fields for inclusion in prompts.

    Args:
        fields: Dictionary of collected fields

    Returns:
        Formatted fields string
    """
    if not fields:
        return "No information collected yet."

    formatted = []
    for key, value in fields.items():
        if value is not None:
            formatted.append(f"- {key}: {value}")

    return "\n".join(formatted) if formatted else "No information collected yet."


def format_products(products: List[Any]) -> str:
    """
    Format product list for inclusion in prompts.

    Args:
        products: List of Product objects

    Returns:
        Formatted products string
    """
    if not products:
        return "No products defined."

    formatted = []
    for product in products:
        name = getattr(product, "name", "Unknown")
        description = getattr(product, "description", "")
        formatted.append(f"- {name}: {description}")

    return "\n".join(formatted)
