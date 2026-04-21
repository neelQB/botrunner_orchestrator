import requests
from qdrant_client.http.models import VectorParams, Distance
from rag.config.constants import (
    EMBEDDING_SIZE,
    MODEL_NAME,
    DEPLOYMENT,
    DEVICE,
    COHERE_RERANKER_API_KEY,
    COHERE_URL,
    RERANKER_DEPLOYMENT,
    TIMEOUT,
    RERANKER_TOP_K,
)


from emailbot.config.settings import logger
from rag.ETL_Pipeline.embeddings import Embeddings
from rag.Qdrant_initializer import get_qdrant_client


class AdvanceEmbeddings(Embeddings):
    def __init__(self):
        try:
            q_client = get_qdrant_client()
            if q_client is None:
                raise ValueError("Qdrant client is not initialized.")
            super().__init__({}, q_client=q_client)
            self.reranker_key = COHERE_RERANKER_API_KEY
            self.reranker_url = COHERE_URL

            self.reranker_headers = {
                "Content-Type": "application/json",
                "api-key": self.reranker_key,
            }
            self.device = DEVICE

        except Exception as e:
            logger.error(f"Error initializing QdrantClient: {e}")
            raise

    def _generate_dense_embedding(self, query: str):
        try:
            response = self.client.embeddings.create(model=DEPLOYMENT, input=query)
            dense_vectors = [data.embedding for data in response.data]
            return dense_vectors

        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            return []

    def get_reranker_scores(self, query, documents):
        try:
            payload = {
                "model": RERANKER_DEPLOYMENT,
                "query": query,
                "documents": documents,
                "top_n": RERANKER_TOP_K,
            }
            response = requests.post(
                url=self.reranker_url,
                headers=self.reranker_headers,
                json=payload,
                timeout=TIMEOUT,
            )
            reranker_context = [
                documents[item["index"]] for item in response.json()["results"]
            ]
            logger.info(f"final reranker count : {len(reranker_context)}")
            return reranker_context

        except Exception as e:
            logger.error(f"Error getting reranker scores: {e}")
            return []

    def get_collection(self, collection_name: str):
        try:
            collection_info = self.Q_client.get_collection(
                collection_name=collection_name
            )
            logger.info(f"Collection {collection_name} already exists")
            return collection_info
        except Exception as e:
            logger.warning(f"Error while getting collection ({collection_name}): {e}")
            logger.info(f"model name : {MODEL_NAME}")
            self.Q_client.create_collection(
                collection_name=collection_name,
                vectors_config={
                    MODEL_NAME: VectorParams(
                        size=EMBEDDING_SIZE, distance=Distance.COSINE
                    )
                },
            )
            collection_info = self.Q_client.get_collection(
                collection_name=collection_name
            )
            logger.info(f"✅ Created new collection: {collection_name}")

            return collection_info
