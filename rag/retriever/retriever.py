from dataclasses import dataclass
from typing import Dict
from . import AdvanceEmbeddings


from emailbot.config.settings import logger
from qdrant_client.models import NamedVector
from rag.config.constants import DENSE_VECTOR_TOP_K, MODEL_NAME


@dataclass
class RetrievedDocument:
    """Data class for retrieved documents"""

    content: str
    score: float

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "content": self.content,
            "source": self.source,
            "doc_id": self.doc_id,
            "chunk_index": self.chunk_index,
            "score": self.score,
            "tenant_id": self.tenant_id,
            "kb_id": self.kb_id,
        }


class Retriever:
    def __init__(self):
        try:
            self.embedder = AdvanceEmbeddings()
        except Exception as e:
            logger.error(f"Error initializing Retriever: {e}")
            raise RuntimeError(f"Failed to initialize Retriever: {e}")

    def retrieve_General_QA(
        self,
        query,
        dense_vectors,
        tenant_id_QA: str,
        kb_ids: list = None,
    ) -> list:
        try:
            final_reranker_context_QA = []
            reranker_context_QA = []

            collection_info = self.embedder.get_collection(collection_name=tenant_id_QA)
            try:
                if collection_info.points_count == 0:
                    logger.info(f"Skipping empty collection for QA: {tenant_id_QA}")
                logger.info(
                    f"Searching collection for QA: {tenant_id_QA} ({collection_info.points_count} points)"
                )

                if dense_vectors is not None:
                    pre_context = self.embedder.Q_client.search(
                        collection_name=tenant_id_QA,
                        query_vector=NamedVector(
                            name=MODEL_NAME, vector=dense_vectors[0]
                        ),
                        limit=10,
                        with_payload=True,
                    )

                    query_text_pairs = [
                        (query, point.payload.get("document", ""))
                        for point in pre_context
                    ]
                    scores = self.embedder.get_reranker_scores(query_text_pairs)

                    for score, point in zip(scores, pre_context):
                        reranker_context_QA.append(
                            RetrievedDocument(
                                content=point.payload.get("document", ""),
                                score=score,
                            )
                        )
                    reranker_context_QA.sort(key=lambda x: x.score, reverse=True)
                    top_docs = reranker_context_QA[:5]
                    final_reranker_context_QA = [doc.content for doc in top_docs]

                    logger.info(
                        f"Final reranker context count for QA: {len(final_reranker_context_QA)}"
                    )
            except Exception as e:
                logger.warning(f"Error searching collection for QA {tenant_id_QA}: {e}")
            return final_reranker_context_QA
        except Exception as e:
            logger.error(f"Error during retrieval for QA: {e}")
            return []

    def retrieve(
        self,
        query,
        tenant_id: str,
        kb_ids: list = None,
    ) -> list:

        try:

            logger.info(f"Query: {query if len(query) < 100 else query[:100] + '...'}")
            dense_vectors = self.embedder._generate_dense_embedding(query=query)

            # final_result_QA = self.retrieve_General_QA(
            #     query=query,
            #     dense_vectors=dense_vectors,
            #     tenant_id_QA="general_QA0f663aa3561a441f9a45a075260bb19f",
            #     kb_ids=kb_ids,
            # )

            collection_info = self.embedder.get_collection(collection_name=tenant_id)
            try:
                if collection_info.points_count == 0:
                    logger.info(f"Skipping empty collection: {tenant_id}")
                logger.info(
                    f"Searching collection: {tenant_id} ({collection_info.points_count} points)"
                )

                if dense_vectors is not None:
                    pre_context = self.embedder.Q_client.search(
                        collection_name=tenant_id,
                        query_vector=NamedVector(
                            name=MODEL_NAME, vector=dense_vectors[0]
                        ),
                        limit=DENSE_VECTOR_TOP_K,
                        with_payload=True,
                    )

                    documents = [
                        point.payload.get("document", "") for point in pre_context
                    ]
                    logger.info(f"documents from precontext : {documents}")
                    final_reranker_context = self.embedder.get_reranker_scores(
                        query, documents
                    )

                    logger.info(f"Final reranker context : {final_reranker_context}")
            except Exception as e:
                logger.warning(f"Error searching collection {tenant_id}: {e}")

            return final_reranker_context
        except Exception as e:
            logger.error(f"Error during retrieval: {e}")
            return []
