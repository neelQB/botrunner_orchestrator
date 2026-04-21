import os
import litellm
from litellm import Router
from opik.integrations.litellm import track_completion
from agents.extensions.models.litellm_model import LitellmModel
from typing import Any, AsyncIterator
from agents.model_settings import ModelSettings
from agents.tool import Tool
from agents.handoffs import Handoff
from agents.models.interface import ModelTracing
from agents.items import TResponseInputItem, TResponseStreamEvent
from agents.agent_output import AgentOutputSchemaBase
from agents.models.chatcmpl_converter import Converter

# Import settings from config
from emailbot.config import settings

# Import prompt cache utilities
from emailbot.utils.prompt_cache import split_cached_prompt, cache_monitor

# Model name configuration from settings
PRIMARY_MODEL = settings.primary_model                         # azure/gpt-5.1-chat
GUARDRAIL_MODEL = settings.guardrail_model                     # azure/gpt-4.1-nano
SUMMARIZER_MODEL = settings.summarizer_model                   # azure/gpt-4.1-nano
OPENAI_FALLBACK_PRIMARY_MODEL = settings.openai_fallback_primary_model    # gpt-5.1-chat-latest
OPENAI_FALLBACK_GUARDRAIL_MODEL = settings.openai_fallback_guardrail_model  # gpt-4.1-nano
OPENAI_FALLBACK_SUMMARIZER_MODEL = settings.openai_fallback_summarizer_model  # gpt-4.1-nano
GEMINI_FALLBACK_MODEL = settings.gemini_fallback_model         # gemini/gemini-3-flash-preview


def _is_gpt5_model(model_name: str) -> bool:
    """Check if the model is a GPT-5 family model that supports reasoning_effort."""
    model_lower = model_name.lower()
    return "gpt-5" in model_lower or "gpt5" in model_lower


def _build_azure_primary_litellm_params() -> dict:
    """Build litellm_params for Azure primary model (gpt-5.1-chat) with conditional reasoning support."""
    params = {
        "model": PRIMARY_MODEL,
        "api_key": settings.azure_openai_key,
        "api_base": settings.azure_openai_endpoint,
        "api_version": settings.azure_api_version,
        "base_model": settings.azure_openai_model_name,   # e.g. "gpt-5.1-chat" for cost/token tracking
        "drop_params": True,
    }

    if _is_gpt5_model(PRIMARY_MODEL):
        params["reasoning_effort"] = "medium"
    else:
        params["temperature"] = 0.7

    return params


def _build_azure_nano_litellm_params(model_name: str) -> dict:
    """Build litellm_params for Azure gpt-4.1-nano models (guardrail & summarizer)."""
    return {
        "model": model_name,
        "api_key": settings.azure_openai_key,
        "api_base": settings.azure_openai_endpoint,
        "api_version": settings.azure_nano_api_version,
        "base_model": "gpt-4.1-nano",   # for accurate cost/token tracking
        "drop_params": True,
    }


def _build_openai_fallback_primary_params() -> dict:
    """Build litellm_params for OpenAI fallback primary model."""
    params = {
        "model": OPENAI_FALLBACK_PRIMARY_MODEL,
        "api_key": settings.openai_api_key,
    }

    if _is_gpt5_model(OPENAI_FALLBACK_PRIMARY_MODEL):
        params["reasoning_effort"] = "medium"
    else:
        params["temperature"] = 0.7

    return params


# 1. Define Model List (Migrated from config.yaml)
# Primary models: Azure  |  Fallback: OpenAI  |  Final fallback: Gemini
MODEL_LIST = [
    # ── Azure primary models ──────────────────────────────────────────
    {
        "model_name": "primary",
        "litellm_params": _build_azure_primary_litellm_params(),
    },
    {
        "model_name": "guardrail",
        "litellm_params": _build_azure_nano_litellm_params(GUARDRAIL_MODEL),
    },
    {
        "model_name": "summarizer",
        "litellm_params": _build_azure_nano_litellm_params(SUMMARIZER_MODEL),
    },
    # ── OpenAI fallback models (role-specific) ────────────────────────
    {
        "model_name": "fallback-primary",
        "litellm_params": _build_openai_fallback_primary_params(),
    },
    {
        "model_name": "fallback-guardrail",
        "litellm_params": {
            "model": OPENAI_FALLBACK_GUARDRAIL_MODEL,
            "api_key": settings.openai_api_key,
        },
    },
    {
        "model_name": "fallback-summarizer",
        "litellm_params": {
            "model": OPENAI_FALLBACK_SUMMARIZER_MODEL,
            "api_key": settings.openai_api_key,
        },
    },
    # ── Gemini final fallback ─────────────────────────────────────────
    {
        "model_name": "fallback-gemini",
        "litellm_params": {
            "model": GEMINI_FALLBACK_MODEL,
            "api_key": settings.gemini_api_key,
        },
    },
]

# 2. Define Router Settings
LITELLM_SETTINGS = {
    "num_retries": 0,
    "timeout": 240,  # Router uses 'timeout' not 'request_timeout'
}

# Set global allowed fallback errors
litellm.allowed_fallback_errors = [
    "rate_limit",
    "insufficient_quota",
    "timeout",
    "internal_server_error",
    "bad_gateway",
    "service_unavailable",
    "context_length_exceeded",
    "authentication_error",
    "invalid_request_error",
    "unauthorized_error",
    "forbidden_error",
    "not_found_error",
    "authentication",
    "invalid_api_key",
    "AuthenticationError",
]

# 3. Define Fallback Strategy (role-specific)
# primary (Azure) → fallback-primary (OpenAI) → fallback-gemini (Gemini)
# guardrail (Azure) → fallback-guardrail (OpenAI) → fallback-gemini
# summarizer (Azure) → fallback-summarizer (OpenAI) → fallback-gemini
FALLBACKS = [
    {"primary": ["fallback-primary", "fallback-gemini"]},
    {"guardrail": ["fallback-guardrail", "fallback-gemini"]},
    {"summarizer": ["fallback-summarizer", "fallback-gemini"]},
    {"fallback-primary": ["fallback-gemini"]},
    {"fallback-guardrail": ["fallback-gemini"]},
    {"fallback-summarizer": ["fallback-gemini"]},
]

# 4. Initialize Router
router = Router(model_list=MODEL_LIST, fallbacks=FALLBACKS, **LITELLM_SETTINGS)

# 5. Patch Router for Opik Tracing
# router.acompletion = track_completion()(router.acompletion)


from contextvars import ContextVar

# A ContextVar to securely temporarily hold the actual model string within the context of a litellm API call
# (Used to bypass the agents SDK ModelResponse stripping the raw model attributes)
_actual_model_var: ContextVar[str | None] = ContextVar("_actual_model_var", default=None)

# 6. Implement RouterModel for Agents SDK
class RouterModel(LitellmModel):
    """
    A custom model class that uses a global litellm.Router.
    """

    def __init__(self, model: str, tenant_id: str | None = None):
        super().__init__(model=model)
        self.tenant_id = tenant_id or None

    async def get_response(self, *args, **kwargs):
        # We override get_response to capture the actual model name safely
        # before the agents SDK drops it while wrapping it in "ModelResponse".
        _actual_model_var.set(None)
        
        # Call the parent LitellmModel.get_response (this will internally call our _fetch_response)
        resp = await super().get_response(*args, **kwargs)
        
        # After it returns, if we captured an actual model name in _fetch_response, tag it onto the ModelResponse
        actual = _actual_model_var.get()
        if actual:
            setattr(resp, "_actual_model_name", actual)
            
        return resp


    async def _fetch_response(
        self,
        system_instructions: str | None,
        input: str | list[TResponseInputItem],
        model_settings: ModelSettings = ModelSettings(prompt_cache_retention="24h"),
        tools: list[Tool] | None = None,  
        output_schema: AgentOutputSchemaBase | None = None,
        handoffs: list[Handoff] | None = None,
        span: Any | None = None,  # Span[GenerationSpanData]
        tracing: ModelTracing | None = None,
        stream: bool = False,
        prompt: Any | None = None,
    ):
        """
        Override to use the global router instead of direct litellm.acompletion.
        """
        import time
        from agents.extensions.models.litellm_model import (
            LitellmConverter,
            FAKE_RESPONSES_ID,
            Response,
            OpenAIResponsesConverter,
            omit,
        )
        from litellm.types.utils import ModelResponse as LiteLLMModelResponse

        converted_messages = Converter.items_to_messages(
            input, preserve_thinking_blocks=(model_settings.reasoning is not None)
        )

        # Split system instructions for prompt prefix caching
        # Static content becomes the first system message (cached by OpenAI)
        # Dynamic content becomes the second system message (not cached)
        if system_instructions:
            if settings.enable_prompt_caching:
                static_part, dynamic_part = split_cached_prompt(system_instructions)
                if dynamic_part:
                    # Insert dynamic context first (will be pushed to index 1)
                    converted_messages.insert(
                        0, {"role": "system", "content": dynamic_part}
                    )
                    # Insert static instructions at index 0 (cached prefix)
                    converted_messages.insert(
                        0, {"role": "system", "content": static_part}
                    )
                else:
                    converted_messages.insert(
                        0, {"role": "system", "content": system_instructions}
                    )
            else:
                converted_messages.insert(
                    0, {"role": "system", "content": system_instructions}
                )

        converted_tools = [Converter.tool_to_openai(t) for t in tools] if tools else []
        for h in handoffs:
            converted_tools.append(Converter.convert_handoff_tool(h))

        extra_kwargs = {}
        if model_settings.extra_args and model_settings.extra_args is not omit:
            extra_kwargs = model_settings.extra_args.copy()

        # Handle structured output schema
        if output_schema is not None:
            json_schema = output_schema.json_schema()
            extra_kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "output",
                    "schema": json_schema,
                    "strict": output_schema.is_strict_json_schema(),
                },
            }

        # Determine if the selected model supports prompt caching.
        model_name = self.model if isinstance(self.model, str) else ""
        prompt_cache_supported = "gemini" not in model_name.lower()
        prompt_cache_key = self.tenant_id if prompt_cache_supported else None
        # Build kwargs for router call, including prompt_cache_key only when supported.
        router_kwargs = dict(
            model=self.model,
            messages=converted_messages,
            tools=converted_tools if converted_tools else None,
            tool_choice=self._remove_not_given(
                OpenAIResponsesConverter.convert_tool_choice(model_settings.tool_choice)
            ),
            max_tokens=self._remove_not_given(model_settings.max_tokens),
            temperature=self._remove_not_given(model_settings.temperature),
            top_p=self._remove_not_given(model_settings.top_p),
            stream=stream,
            **extra_kwargs,
        )
        if prompt_cache_key is not None:
            router_kwargs["prompt_cache_key"] = prompt_cache_key
        ret = await router.acompletion(**router_kwargs)

        if isinstance(ret, LiteLLMModelResponse):
            # Record prompt cache statistics from response
            cache_monitor.record(ret, model=self.model)

            # ── Resolve the real model name ────────────────────────────────────
            # `ret.model` is set by litellm directly from the API response body,
            # so it holds the ACTUAL model used (e.g. "gpt-5.1-chat-latest" when
            # the OpenAI fallback fired).  `self.model` is the router ALIAS
            # (e.g. "primary") and will be used by the agents SDK for its own
            # Response wrapper — which is why raw_responses later show the alias.
            #
            # We detect fallback via the header litellm injects:
            #   _hidden_params.additional_headers["x-litellm-attempted-fallbacks"]
            # When that header is present and > 0 a fallback occurred, and
            # ret.model already holds the fallback model's real name.
            #
            # Even without a fallback, ret.model is more accurate than self.model
            # (e.g. Azure returns the deployment name vs the alias "primary").
            hidden = getattr(ret, "_hidden_params", None) or {}
            # HiddenParams may be a pydantic object — access via .get()
            if hasattr(hidden, "get"):
                additional_headers = hidden.get("additional_headers") or {}
            else:
                additional_headers = {}
            attempted_fallbacks = additional_headers.get("x-litellm-attempted-fallbacks", 0)

            if attempted_fallbacks and attempted_fallbacks > 0:
                # A fallback occurred: ret.model is the real fallback model name
                actual_model = ret.model or self.model
                logger.debug(
                    f"[route] Fallback detected (depth={attempted_fallbacks}): "
                    f"alias='{self.model}' → actual='{actual_model}'"
                )
            else:
                # No fallback: ret.model is the real primary model from the API
                actual_model = ret.model or self.model

            # Expose the actual model used securely so we don't depend on the agents SDK preserving it
            _actual_model_var.set(actual_model)
            return ret

        responses_tool_choice = OpenAIResponsesConverter.convert_tool_choice(
            model_settings.tool_choice
        )
        if responses_tool_choice is None or responses_tool_choice is omit:
            responses_tool_choice = "auto"

        response = Response(
            id=FAKE_RESPONSES_ID,
            created_at=time.time(),
            model=self.model,
            object="response",
            output=[],
            tool_choice=responses_tool_choice,  # type: ignore
            top_p=model_settings.top_p,
            temperature=model_settings.temperature,
            tools=[],
            parallel_tool_calls=model_settings.parallel_tool_calls or False,
            reasoning=model_settings.reasoning,
        )
        return response, ret

    def _remove_not_given(self, value: Any) -> Any:
        from openai import NotGiven
        from agents.extensions.models.litellm_model import omit

        if value is omit or isinstance(value, NotGiven):
            return None
        return value
