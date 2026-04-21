# emailbot/cache/session_cache.py

from collections import deque
from typing import Dict, List, Any, Optional
import numpy as np
import os
from sklearn.metrics.pairwise import cosine_similarity
from emailbot.core.state import BotState
from emailbot.config.settings import logger
from emailbot.config import settings as _settings

# =========================
# CONFIG
# =========================
MAX_PAIRS = 15
TOP_K = 3
SIMILARITY_THRESHOLD = 0.5

# =========================
# GLOBAL CACHE
# =========================
SESSION_CACHE: Dict[str, Dict] = {}

# =========================
# EMBEDDING MODEL 
# =========================
# Environment-based Azure settings
# AZURE_EMBED_ENDPOINT = os.getenv("AZURE_EMBED_ENDPOINT")
# AZURE_EMBED_DEPLOYMENT = (
#     os.getenv("AZURE_EMBED_DEPLOYMENT")
#     or os.getenv("AZURE_EMBED_MODEL")
#     or os.getenv("EMBEDDING_MODEL")
# )
# AZURE_INFERENCE_KEY = (
#     os.getenv("AZURE_INFERENCE_CREDENTIAL")
#     or os.getenv("AZURE_OPENAI_KEY")
#     or os.getenv("AZURE_API_KEY")
# )
AZURE_EMBED_ENDPOINT = _settings.AZURE_EMBED_ENDPOINT
AZURE_INFERENCE_KEY = _settings.azure_inference_credential
AZURE_EMBED_DEPLOYMENT = _settings.embedding_model
# Clients / models (initialized once)
_embedding_client = None
_embedding_model = None
_embedding_is_azure = False

try:
    from openai import AzureOpenAI

    # api_version = os.getenv("AZURE_API_VERSION", "2025-03-01-preview")
    api_version = _settings.azure_api_version
    _embedding_client = AzureOpenAI(
        api_version=api_version,
        azure_endpoint=AZURE_EMBED_ENDPOINT,
        api_key=AZURE_INFERENCE_KEY,
    )
    logger.info(f"Initialize AZURE Embedding Model")
    _embedding_is_azure = True
    
except Exception as e:
    logger.error(f"Failed to initialize embedding client: {e}")
    _embedding_client = None
    _embedding_model = None


def _embed(text: str) -> np.ndarray:
    """Return embedding vector for `text` as a numpy array.

    Uses Azure OpenAI embeddings when AZURE env vars are set, otherwise
    uses a local SentenceTransformer if available.
    """
    if _embedding_is_azure and _embedding_client is not None:
        resp = _embedding_client.embeddings.create(model=AZURE_EMBED_DEPLOYMENT, input=text)
        emb = resp.data[0].embedding
        return np.array(emb, dtype=float)

    if _embedding_model is not None:
        # SentenceTransformer.encode uses convert_to_numpy in some versions
        try:
            return _embedding_model.encode(text, convert_to_numpy=True)
        except TypeError:
            # Fallback for older/newer versions
            return np.array(_embedding_model.encode(text))

    raise RuntimeError(
        "No embedding model configured. Set AZURE_EMBED_ENDPOINT and AZURE_EMBED_DEPLOYMENT or EMBEDDING_MODEL environment variables."
    )


# =========================
# SESSION MANAGEMENT
# =========================
def init_session(user_id: str):
    SESSION_CACHE[user_id] = {
        # Store ONLY (user_query, assistant_answer) pairs
        "qa_pairs": deque(maxlen=MAX_PAIRS)
    }


def get_session(user_id: str):
    return SESSION_CACHE.get(user_id)


def update_session(
    user_id: str, user_text: str, assistant_text: Any, state: Any = BotState
):
    """
    Store a single user/assistant pair in cache
    """
    if user_id not in SESSION_CACHE:
        init_session(user_id)

    # Extract plain text for the assistant response if it's an object
    display_text = assistant_text
    if not isinstance(assistant_text, str):
        if hasattr(assistant_text, "final_output"):
            if hasattr(assistant_text.final_output, "response"):
                display_text = assistant_text.final_output.response
            else:
                display_text = str(assistant_text.final_output)
        elif isinstance(assistant_text, dict):
            display_text = (
                assistant_text.get("response")
                or assistant_text.get("answer")
                or str(assistant_text)
            )
        else:
            display_text = str(assistant_text)

    updated_state = state if state else BotState

    # Pre-compute embedding for the user query so retrieve_from_cache
    # doesn't need to call the embedding API for every cached pair.
    try:
        user_embedding = _embed(user_text)
    except Exception as e:
        logger.warning(f"Failed to pre-compute embedding for cache entry: {e}")
        user_embedding = None

    SESSION_CACHE[user_id]["qa_pairs"].append(
        {
            "user": user_text,
            "assistant": display_text,
            "full_result": (
                assistant_text if not isinstance(assistant_text, str) else None
            ),
            "state": updated_state,
            "embedding": user_embedding,
        }
    )

    # logger.info(f"Updated session cache {SESSION_CACHE[user_id]}")


# =========================
# SEMANTIC RETRIEVAL
# =========================
def retrieve_from_cache(
    user_id: str,
    user_query: str,
    top_k: int = TOP_K,
    similarity_threshold: float = SIMILARITY_THRESHOLD,
) -> List[Dict]:
    """
    Compare current user query with cached user queries
    and return relevant Q/A pairs
    """

    session = get_session(user_id)
    if not session or not session["qa_pairs"]:
        return []

    query_embedding = _embed(user_query).reshape(1, -1)

    results = []

    for pair in session["qa_pairs"]:
        # Use pre-computed embedding if available, otherwise compute on the fly
        cached_embedding = pair.get("embedding")
        if cached_embedding is None:
            try:
                cached_embedding = _embed(pair["user"])
            except Exception:
                continue
        cached_embedding = cached_embedding.reshape(1, -1)

        score = cosine_similarity(query_embedding, cached_embedding)[0][0]

        if score >= similarity_threshold:
            results.append(
                {
                    "user": pair["user"],
                    "assistant": pair["assistant"],
                    "score": float(score),
                }
            )

    # Sort by similarity
    results.sort(key=lambda x: x["score"], reverse=True)

    return results[:top_k]
