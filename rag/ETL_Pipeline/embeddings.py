

from emailbot.config.settings import logger
from openai import AzureOpenAI
from rag.config.constants import (
    DEPLOYMENT,
    API_VERSION,
    AZURE_EMBED_ENDPOINT,
    AZURE_INFERENCE_CREDENTIAL,
)


class Embeddings:
    def __init__(self, logger_extra, q_client):
        self.logger_extra = logger_extra
        self.dense_endpoint = AZURE_EMBED_ENDPOINT
        self.dense_key = AZURE_INFERENCE_CREDENTIAL
        self.client = AzureOpenAI(
            api_version=API_VERSION,
            azure_endpoint=self.dense_endpoint,
            api_key=self.dense_key,
        )
        try:
            self.Q_client = q_client
            if self.Q_client is None:
                raise ValueError("Qdrant client is not initialized.")
        except Exception as e:
            logger.error(f"Error initializing clients: {e}", extra=self.logger_extra)
            raise

    def get_dense_embeddings(self, texts: str):
        try:
            response = self.client.embeddings.create(model=DEPLOYMENT, input=texts)
            embeddings = [data.embedding for data in response.data]
            return embeddings
        except Exception as e:
            logger.error(
                f"Azure API failed for embbeding: {e}", extra=self.logger_extra
            )
            raise
            # return []

    def get_all_collections_for_tenant(
        self, tenant_id: str, kb_ids: list = None
    ) -> list:
        try:
            tenant_collections = []

            return tenant_collections
        except Exception as e:
            logger.error(
                f"Error retrieving collections for tenant {tenant_id}: {e}",
                extra=self.logger_extra,
            )
            return []
