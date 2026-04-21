import os
from datetime import datetime, UTC
from emailbot.config.settings import Settings
Settings()

def get_current_time():
    now = datetime.now(UTC)
    return now


current_time_str = get_current_time()

# ------------------------------------MODEL CONSTANTS------------------------------------------

DEVICE = "cpu"

# ------------------------------------AZURE EMBEDDING MODEL CONSTANTS------------------------------------------

# AZURE_EMBED_ENDPOINT = os.getenv("AZURE_EMBED_ENDPOINT")
AZURE_EMBED_ENDPOINT = Settings().AZURE_EMBED_ENDPOINT
# AZURE_INFERENCE_CREDENTIAL = os.getenv("AZURE_INFERENCE_CREDENTIAL")
AZURE_INFERENCE_CREDENTIAL = Settings().azure_inference_credential
EMBEDDING_SIZE = 1536
DENSE_VECTOR_TOP_K = 5
DEPLOYMENT = "text-embedding-3-small"
MODEL_NAME = "text-embedding-3-small"
API_VERSION = "2024-12-01-preview"

# ------------------------------------COHERE RERANKER CONSTANTS------------------------------------------

# COHERE_RERANKER_API_KEY = os.getenv("COHERE_RERANKER_API_KEY")
COHERE_RERANKER_API_KEY = Settings().cohere_reranker_api_key
# COHERE_URL = os.getenv("COHERE_URL")
COHERE_URL = Settings().cohere_url
RERANKER_DEPLOYMENT = "cohere-rerank-v4.0-fast"
RERANKER_TOP_K = 5

# ------------------------------------QDRANT CONSTANTS------------------------------------------

# QDRANT_HOST = os.getenv("QDRANT_HOST")
QDRANT_HOST = Settings().qdrant_host
# QDRANT_PORT = os.getenv("QDRANT_PORT")
QDRANT_PORT = Settings().qdrant_port

# QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_URL = Settings().qdrant_url
# QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
QDRANT_API_KEY = Settings().qdrant_api_key

QDRANT_UPSERTING_BATCH_SIZE = 50

# ------------------------------------GEMINI CONSTANTS------------------------------------------

# GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_API_KEY = Settings().gemini_api_key

# ------------------------------------OTHER CONSTANTS------------------------------------------

# MAX_HISTORY = 15
MAX_HISTORY = Settings().max_history

TIMEOUT = 300
