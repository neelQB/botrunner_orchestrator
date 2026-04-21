

from emailbot.config.settings import logger
from qdrant_client import QdrantClient
from typing import Optional
from rag.config.constants import (
    QDRANT_HOST,
    QDRANT_PORT,
    QDRANT_URL,
    QDRANT_API_KEY,
)

QDRANT_CONFIG = {
    "url": QDRANT_URL,
    "port": None,
    "api_key": QDRANT_API_KEY,
    "https": False,
    "timeout": 60,
}


def get_qdrant_client():
    try:
        if QDRANT_URL:
            url = QDRANT_URL
        elif QDRANT_HOST:
            port = QDRANT_PORT or 6333
            url = f"http://{QDRANT_HOST}:{port}"
        else:
            url = "http://localhost:6333"

        q_client = QdrantClient(url=url, api_key=QDRANT_API_KEY)
        logger.info(f"Qdrant client initialized successfully for URL: {url}")
        return q_client
    except Exception as e:
        logger.error(f"Failed to initialize Qdrant client: {e}")
        return None


# def get_qdrant_client() -> Optional[QdrantClient]:
#     try:
#         client = QdrantClient(
#             **QDRANT_CONFIG
#         )
#         logger.info("Qdrant client initialized successfully.")
#         return client
#     except AttributeError as e:
#         logger.error(f"Qdrant configuration is missing in settings: {e}")
#         return None
#     except Exception as e:
#         logger.error(f"Failed to initialize Qdrant client: {e}")
#         return None
