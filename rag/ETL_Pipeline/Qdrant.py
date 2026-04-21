from typing import Tuple
from qdrant_client import QdrantClient, models
from qdrant_client.models import VectorParams, Distance
from rag.config.constants import MODEL_NAME, EMBEDDING_SIZE


from emailbot.config.settings import logger
from rag.Qdrant_initializer import get_qdrant_client
from typing import Tuple, Set
import traceback


class QdrantManager:
    Q_client: QdrantClient | None = None

    def __init__(self, logger_extra, tenant_id: str, kb_id: str):
        self.Q_client = get_qdrant_client()
        if self.Q_client is None:
            raise ValueError("Qdrant client is not initialized.")

        self.logger_extra = logger_extra
        self.collection_name = tenant_id
        self.get_collection()

    def get_qclient(self):
        if self.Q_client is None:
            logger.info(f"Qdrant client is not initialized", extra=self.logger_extra)
        return self.Q_client

    def get_collection(self):
        try:
            self.Q_client.get_collection(collection_name=self.collection_name)
            logger.info(
                f"Collection {self.collection_name} already exists",
                extra=self.logger_extra,
            )
        except Exception as e:
            logger.warning(
                f"Collection {self.collection_name} not found or error accessing it. Attempting to create...",
                extra=self.logger_extra,
            )
            logger.info(f"model name : {MODEL_NAME}", extra=self.logger_extra)
            self.Q_client.create_collection(
                collection_name=self.collection_name,
                vectors_config={
                    MODEL_NAME: VectorParams(
                        size=EMBEDDING_SIZE, distance=Distance.COSINE
                    )
                },
            )
            logger.info(
                f"✅ Created new collection: {self.collection_name}",
                extra=self.logger_extra,
            )

    def delete_from_qdrant(
        self, kb_id, doc_id=None, is_full_delete=False
    ) -> Tuple[bool, str]:
        try:
            if is_full_delete:
                self.Q_client.delete(
                    collection_name=self.collection_name,
                    points_selector=models.FilterSelector(
                        filter=models.Filter(
                            must=[
                                models.FieldCondition(
                                    key="kb_id", match=models.MatchValue(value=kb_id)
                                )
                            ]
                        )
                    ),
                )
                msg = f"Deleted all chunks for kb_id: {kb_id} from collection: {self.collection_name}"
                logger.info(msg, extra=self.logger_extra)
                return True, msg
            else:
                self.Q_client.delete(
                    collection_name=self.collection_name,
                    points_selector=models.FilterSelector(
                        filter=models.Filter(
                            must=[
                                models.FieldCondition(
                                    key="doc_id", match=models.MatchValue(value=doc_id)
                                ),
                                models.FieldCondition(
                                    key="kb_id", match=models.MatchValue(value=kb_id)
                                ),
                            ]
                        )
                    ),
                )
                msg = f"Deleted all chunks for doc_id: {doc_id} from collection: {self.collection_name}"
                logger.info(msg, extra=self.logger_extra)
                return True, msg
        except Exception as e:
            error_msg = f"Error deleting from Qdrant: {e}"
            logger.error(error_msg, extra=self.logger_extra)
            return False, error_msg

    def upsert_collection(self, collection_name: str, points: int):
        try:
            self.Q_client.upsert(collection_name=collection_name, points=points)
        except Exception as e:
            error_message = f"error upserting to qdrant: {e}"
            logger.error(error_message, extra=self.logger_extra)

    def get_processed_ids(self, kb_id, scroll_limit=10000):
        try:
            unique_doc_ids: Set[str] = set()

            results = self.Q_client.scroll(
                collection_name=self.collection_name,
                scroll_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="kb_id", match=models.MatchValue(value=kb_id)
                        )
                    ]
                ),
                with_payload=["doc_id"],
                limit=scroll_limit,
            )

            points, next_page = results
            for point in points:
                if point.payload and "doc_id" in point.payload:
                    unique_doc_ids.add(point.payload["doc_id"])

            while next_page is not None:
                points, next_page = self.Q_client.scroll(
                    collection_name=self.collection_name,
                    scroll_filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="kb_id", match=models.MatchValue(value=kb_id)
                            )
                        ]
                    ),
                    with_payload=["doc_id"],
                    limit=scroll_limit,
                    offset=next_page,
                )
                for point in points:
                    if point.payload and "doc_id" in point.payload:
                        unique_doc_ids.add(point.payload["doc_id"])

            self.ids = list(unique_doc_ids)

            logger.info(f"Processed ids : {self.ids}")
            return True, self.ids, "Processed ids fetched successfully"
        except Exception as e:
            error_message = f"Error fetching processed ids from Qdrant: {e}"
            logger.error(error_message, extra=self.logger_extra)
            self.ids = []
            return False, self.ids, error_message

    # def get_processed_ids(self):
    #     try:
    #         pass
    #     except Exception as e:
