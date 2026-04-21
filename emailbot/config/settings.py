"""
Application Settings - Environment-based configuration using Pydantic.

This module provides a centralized settings class that loads configuration
from environment variables with validation and type coercion.

Environment Variables:
    - DATABASE_URL: Database connection string
    - DATABASE: Database type ("neon" or "SQLite")
    - OPENAI_API_KEY: OpenAI API key
    - AZURE_OPENAI_KEY: Azure OpenAI API key
    - etc.

Usage:
    from emailbot.config.settings import settings
    
    print(settings.database_url)
    print(settings.openai_api_key)
"""

import os
from enum import Enum
from functools import lru_cache
from typing import Optional, List

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import logging
logger = logging.getLogger(__name__)

class Environment(str, Enum):
    """Application environment types."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TESTING = "testing"


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    Uses Pydantic BaseSettings for automatic env loading, validation,
    and type coercion.

    Attributes:
        environment: Current environment (dev/staging/prod)
        debug: Enable debug mode

        # Database
        database_url: Database connection string
        database_type: "neon" or "SQLite"

        # Vector Database
        qdrant_host: Qdrant server host
        qdrant_port: Qdrant server port

        # OpenAI
        openai_api_key: OpenAI API key
        openai_base_url: OpenAI base URL
        openai_model_name: OpenAI model name

        # Azure OpenAI
        azure_openai_key: Azure OpenAI API key
        azure_openai_endpoint: Azure OpenAI endpoint
        azure_api_version: Azure API version
        azure_openai_model_name: Azure model name

        # Gemini
        gemini_api_key: Gemini API key
        gemini_base_url: Gemini base URL
        gemini_model_name: Gemini model name

        # Embeddings
        AZURE_EMBED_ENDPOINT: Azure embedding endpoint
        azure_inference_credential: Azure inference credential

        # Reranking
        azure_cross_encoder_endpoint: Azure cross encoder endpoint
        azure_cross_encoder_credential: Azure cross encoder credential
        cohere_reranker_api_key: Cohere reranker API key
        cohere_url: Cohere API URL

        # Opik (Observability)
        opik_project_name: Opik project name
        opik_workspace: Opik workspace

        # Summarizer
        summarize_context_length: Context length for summarization
        summarize_keep_last_n_turns: Number of turns to keep

        # History
        max_history: Maximum chat history messages
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Environment
    environment: Environment = Field(
        default=Environment.DEVELOPMENT, description="Application environment"
    )
    debug: bool = Field(default=False, description="Enable debug mode")

    # Database Configuration
    database_url: Optional[str] = Field(
        default=None, description="Database connection URL"
    )
    database_type: str = Field(
        default="SQLite", alias="DATABASE", description="Database type"
    )

   
    qdrant_host: Optional[str] = Field(default=None, alias="QDRANT_HOST", description="Qdrant host")
    qdrant_port: Optional[int] = Field(default=None, alias="QDRANT_PORT", description="Qdrant port")

    # OpenAI Configuration
    openai_api_key: Optional[str] = Field(default=None, description="OpenAI API key")
    openai_base_url: Optional[str] = Field(default=None, description="OpenAI base URL")
    openai_model_name: str = Field(default="gpt-4o", description="OpenAI model name")

    # Azure OpenAI Configuration
    azure_openai_key: Optional[str] = Field(
        default=None, description="Azure OpenAI key"
    )
    azure_openai_endpoint: Optional[str] = Field(
        default=None, description="Azure OpenAI endpoint"
    )
    azure_api_version: str = Field(
        default="2025-03-01-preview", description="Azure API version"
    )
    azure_openai_model_name: str = Field(
        default="gpt-4.1", description="Azure model name"
    )

    # Gemini Configuration
    gemini_api_key: Optional[str] = Field(default=None, description="Gemini API key")
    gemini_base_url: Optional[str] = Field(default=None, description="Gemini base URL")
    gemini_model_name: str = Field(
        default="gemini-3-flash-preview", description="Gemini model name"
    )

    # Embedding Configuration
    AZURE_EMBED_ENDPOINT: Optional[str] = Field(
        default=None, description="Azure embed endpoint"
    )
    azure_inference_credential: Optional[str] = Field(
        default=None, description="Azure inference credential"
    )
    azure_embed_deployment: Optional[str] = Field(
        default=None, description="Azure embed deployment"
    )
    azure_embed_model: Optional[str] = Field(
        default=None, description="Azure embed model"
    )
    embedding_model: Optional[str] = Field(
        default=None, description="Embedding model"
    )
    azure_api_key: Optional[str] = Field(
        default=None, description="Azure API key"
    )


    # Reranking Configuration
    azure_cross_encoder_endpoint: Optional[str] = Field(
        default=None, description="Azure cross encoder endpoint"
    )
    azure_cross_encoder_credential: Optional[str] = Field(
        default=None, description="Azure cross encoder credential"
    )
    cohere_reranker_api_key: Optional[str] = Field(
        default=None, description="Cohere reranker key"
    )
    cohere_url: Optional[str] = Field(default=None, description="Cohere URL")

    # Opik (Observability)
    opik_project_name: Optional[str] = Field(
        default=None, description="Opik project name"
    )
    opik_workspace: Optional[str] = Field(default=None, description="Opik workspace")

    # Summarizer Settings
    summarize_context_length: int = Field(
        default=3,
        alias="SUMMARIZE_CONTEXT_LENGTH",
        description="Context length for summarization",
    )
    summarize_keep_last_n_turns: int = Field(
        default=3,
        alias="SUMMARIZE_KEEP_LAST_N_TURNS",
        description="Number of turns to keep",
    )

    # History Settings
    max_history: int = Field(
        default=15, alias="MAX_HISTORY", description="Maximum history messages"
    )
    
    # SQLAlchemySession Settings
    sqlalchemy_database_url: str = Field(
        default=":memory:",
        alias="SQLALCHEMY_DATABASE_URL",
        description="SQLAlchemy database URL (supports PostgreSQL, MySQL, SQLite, etc.)",
    )
    sessions_id: str = Field(
        default="global_runner_session",
        alias="SESSIONS_ID",
        description="Session ID for SQLAlchemySession",
    )
    enable_session_creation_tables: bool = Field(
        default=True,
        alias="ENABLE_SESSION_CREATION_TABLES",
        description="Auto-create session tables on initialization",
    )
    session_context_window_size: int = Field(
        default=10,
        alias="SESSION_CONTEXT_WINDOW_SIZE",
        description="Context window size (number of messages to keep in context)",
    )

    # Prompt Caching
    enable_prompt_caching: bool = Field(
        default=True,
        alias="ENABLE_PROMPT_CACHING",
        description="Enable prompt prefix caching (splits static/dynamic system messages)",
    )

    # Model Configuration — Azure as primary, OpenAI as fallback
    primary_model: str = Field(
        default="azure/gpt-5.1-chat",
        alias="PRIMARY_MODEL",
        description="Primary chat model (Azure deployment)",
    )
    guardrail_model: str = Field(
        default="azure/gpt-4.1-nano",
        alias="GUARDRAIL_MODEL",
        description="Guardrail model for input/output validation (Azure)",
    )
    summarizer_model: str = Field(
        default="azure/gpt-4.1-nano",
        alias="SUMMARIZER_MODEL",
        description="Model for summarization and executive summaries (Azure)",
    )
    azure_nano_api_version: str = Field(
        default="2025-01-01-preview",
        alias="AZURE_NANO_API_VERSION",
        description="Azure API version for gpt-4.1-nano (guardrail & summarizer)",
    )
    openai_fallback_primary_model: str = Field(
        default="gpt-5.1-chat-latest",
        alias="OPENAI_FALLBACK_PRIMARY_MODEL",
        description="OpenAI fallback for primary model",
    )
    openai_fallback_guardrail_model: str = Field(
        default="gpt-4.1-nano",
        alias="OPENAI_FALLBACK_GUARDRAIL_MODEL",
        description="OpenAI fallback for guardrail model",
    )
    openai_fallback_summarizer_model: str = Field(
        default="gpt-4.1-nano",
        alias="OPENAI_FALLBACK_SUMMARIZER_MODEL",
        description="OpenAI fallback for summarizer model",
    )
    gemini_fallback_model: str = Field(
        default="gemini/gemini-3-flash-preview",
        alias="GEMINI_FALLBACK_MODEL",
        description="Gemini fallback model",
    )

    # Qdrant Configuration
    qdrant_url: Optional[str] = Field(default=None, alias="QDRANT_URL", description="Qdrant URL")
    qdrant_api_key: Optional[str] = Field(default=None, alias="QDRANT_API_KEY", description="Qdrant API key")

    @field_validator("database_type")
    @classmethod
    def validate_database_type(cls, v: str) -> str:
        """Validate database type is supported."""
        valid_types = ["neon", "sqlite", "SQLite"]
        if v.lower() not in [t.lower() for t in valid_types]:
            raise ValueError(f"Database type must be one of {valid_types}, got {v}")
        return v

    @model_validator(mode="after")
    def validate_api_keys(self) -> "Settings":
        """Warn if critical API keys are missing."""
        if self.environment == Environment.PRODUCTION:
            if not self.openai_api_key and not self.azure_openai_key:
                logger.warning(
                    "No OpenAI or Azure OpenAI API key configured in production"
                )
        return self

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == Environment.PRODUCTION

    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment == Environment.DEVELOPMENT

    def get_database_config(self) -> dict:
        """Get database configuration dictionary."""
        return {
            "url": self.database_url,
            "type": self.database_type,
            "path": self.database_path,
        }

    def get_openai_config(self) -> dict:
        """Get OpenAI configuration dictionary."""
        return {
            "api_key": self.openai_api_key,
            "base_url": self.openai_base_url,
            "model_name": self.openai_model_name,
        }

    def get_azure_config(self) -> dict:
        """Get Azure OpenAI configuration dictionary."""
        return {
            "api_key": self.azure_openai_key,
            "endpoint": self.azure_openai_endpoint,
            "api_version": self.azure_api_version,
            "model_name": self.azure_openai_model_name,
        }

    def get_model_config(self) -> dict:
        """Get model configuration dictionary."""
        return {
            "primary_model": self.primary_model,
            "guardrail_model": self.guardrail_model,
            "summarizer_model": self.summarizer_model,
            "openai_fallback_primary_model": self.openai_fallback_primary_model,
            "openai_fallback_guardrail_model": self.openai_fallback_guardrail_model,
            "openai_fallback_summarizer_model": self.openai_fallback_summarizer_model,
            "gemini_fallback_model": self.gemini_fallback_model,
        }


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.

    Uses LRU cache to ensure settings are only loaded once
    and reused throughout the application lifecycle.

    Returns:
        Settings: Application settings instance
    """
    logger.info("Loading application settings from environment")
    return Settings()


# Convenience function for clearing settings cache (useful for testing)
def clear_settings_cache() -> None:
    """Clear the settings cache, forcing reload on next access."""
    get_settings.cache_clear()
    logger.debug("Settings cache cleared")
