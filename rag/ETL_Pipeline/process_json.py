import json
from typing import Tuple, List, Dict


from emailbot.config.settings import logger
from rag.ETL_Pipeline.Qdrant import QdrantManager


def _get_extra(add_dict):
    return add_dict


from rag.ETL_Pipeline.init import (
    KnowledgeBase,
    KBFiles,
    KBText,
    KBWebsite,
    KBQuestions,
    KBQuestionAnswer,
    ETLStatus,
    ETLTracker,
    ETLRecordType,
    model_choices_mapping,
    model_strings,
    string_model_mapping,
    Extractor,
)


class ETLPipeLine:
    data = None
    data_ids = []
    etl_tracker_obj = None
    kb_id = None
    tenant_id = None
    logger_extra = {}
    Q_client = None
    processed_ids = []
    extractor = None

    def __init__(self, json_value, etl_tracker_id, tenant_id, kb_id):
        self.kb_id = kb_id
        self.tenant_id = tenant_id

        if isinstance(json_value, str):
            self.data = json.loads(json_value)
        elif isinstance(json_value, dict):
            self.data = json_value
        else:
            raise ValueError("Input must be a dict or JSON string")

        if etl_tracker_id:
            obj = ETLTracker.objects.filter(id=etl_tracker_id).first()
            if obj:
                self.etl_tracker_obj = obj
            else:
                raise ValueError("ETLTracker id not found")
        else:
            # raise ValueError("ETLTracker id is required")
            pass

        self.logger_extra = _get_extra(
            add_dict={
                "etl_tracker_id": etl_tracker_id,
                "tenant_id": self.tenant_id,
                "kb_id": self.kb_id,
                "collection_name": f"{self.tenant_id}_{self.kb_id}",
            }
        )
        success, message = self.get_ids_from_data()
        if not success:
            raise ValueError(message)
        self.Q_manager = QdrantManager(
            logger_extra=self.logger_extra, tenant_id=self.tenant_id, kb_id=self.kb_id
        )
        self.Q_client = self.Q_manager.Q_client
        if self.Q_client is None:
            raise ValueError("Qdrant client is not initialized.")
        success, self.processed_ids, message = self.Q_manager.get_processed_ids(
            self.kb_id
        )
        if not success:
            raise ValueError(message)

        try:
            self.extractor = Extractor(etl_pipeline=self)
        except Exception as e:
            error_msg = f"Failed to initialize Extractor: {e}"
            logger.error(error_msg, extra=self.logger_extra)
            raise ValueError(error_msg)

    def get_ids_from_data(self) -> Tuple[bool, str]:
        data = self.data
        ids = []
        try:
            if "texts" in data:
                for item in data["texts"]:
                    if "id" in item:
                        ids.append(item["id"])
            if "files" in data:
                for item in data["files"]:
                    if "id" in item:
                        ids.append(item["id"])
            if "websites" in data:
                for item in data["websites"]:
                    if "id" in item:
                        ids.append(item["id"])
            if "question_answers" in data:
                for item in data["question_answers"]:
                    for q in item.get("questions", []):
                        if "id" in q:
                            ids.append(q["id"])
            self.data_ids = ids
            logger.info(
                f"Extracted IDs from data: {self.data_ids}", extra=self.logger_extra
            )

            return True, "Successfully extracted IDs"
        except Exception as e:
            self.data_ids = []
            error_msg = f"Error extracting IDs from data: {e}"
            logger.error(error_msg, extra=self.logger_extra)
            return False, error_msg

    def run_pipeline_from_json(self) -> Tuple[bool, str]:
        overall_success = True
        overall_error_message = None

        try:
            self.update_etl_status(
                model_class=KnowledgeBase,
                instance_id=self.kb_id,
                status=ETLStatus.IN_PROGRESS,
                message="ETL Pipeline started.",
            )
            is_deleted = self.data.get("is_deleted", False)
            if is_deleted:
                success, message = self.Q_manager.delete_from_qdrant(
                    is_full_delete=True, kb_id=self.kb_id
                )

                if not success:
                    self.update_etl_status(
                        model_class=KnowledgeBase,
                        instance_id=self.kb_id,
                        status=ETLStatus.FAILED,
                        message=message,
                    )
                    return False, message
                else:
                    self.update_etl_status(
                        model_class=KnowledgeBase,
                        instance_id=self.kb_id,
                        status=ETLStatus.COMPLETED,
                        message=message,
                    )
                    return True, message
            else:

                os1 = self.extractor.process_all_files_dict()
                os2 = self.extractor.process_all_texts_dict()
                os3 = self.extractor.process_all_website_dict()
                os4 = self.extractor.process_all_questions_answers()

                ids_to_delete = self.processed_ids
                logger.warning(
                    f"IDs to delete: {ids_to_delete}", extra=self.logger_extra
                )
                for id_to_delete in ids_to_delete:
                    success, msg = self.Q_manager.delete_from_qdrant(
                        doc_id=id_to_delete, kb_id=self.kb_id
                    )
                    if not success:
                        logger.error(msg, extra=self.logger_extra)
                    else:
                        logger.info(msg, extra=self.logger_extra)

                if not (os1 and os2 and os3 and os4):
                    overall_success = False

            if overall_success:
                self.update_etl_status(
                    model_class=KnowledgeBase,
                    instance_id=self.kb_id,
                    status=ETLStatus.COMPLETED,
                    message="ETL Pipeline completed successfully.",
                )
                return True, "ETL Pipeline completed successfully."
            else:
                self.update_etl_status(
                    model_class=KnowledgeBase,
                    instance_id=self.kb_id,
                    status=ETLStatus.FAILED,
                    message=overall_error_message if overall_error_message else "",
                )

            final_processed_ids = self.Q_manager.get_processed_ids(kb_id=self.kb_id)
            logger.info(
                f"Final processed IDs after ETL: {final_processed_ids}",
                extra=self.logger_extra,
            )

            return overall_success, (
                overall_error_message if overall_error_message else ""
            )

        except Exception as e:
            error_msg = f"Failed to update ETL status: {e}"
            logger.error(error_msg, extra=self.logger_extra)
            self.update_etl_status(
                model_class=KnowledgeBase,
                instance_id=self.kb_id,
                status=ETLStatus.FAILED,
                message=error_msg,
            )
            return False, error_msg

    def update_etl_status(
        self, model_class, instance_id: str, status: ETLStatus, message: str = ""
    ) -> None:
        try:
            if self.etl_tracker_obj:
                self.etl_tracker_obj.add_etl_status_record(
                    etl_record_type=model_choices_mapping.get(
                        model_class, ETLRecordType.KNOWLEDGE_BASE
                    ),
                    etl_status=status,
                    etl_status_message=message,
                    obj_id=instance_id,
                )
            else:
                logger.debug(
                    f"ETL status record skipped: etl_tracker_obj not available for {instance_id}",
                    extra=self.logger_extra,
                )
            # instance.save(update_fields=['etl_statuses', 'retry_count', 'max_retries'])
            logger.info(
                f"Updated ETL status for {model_class.__name__} {instance_id} to {status}",
                extra=self.logger_extra,
            )

        # except model_class.DoesNotExist:
        #     logger.error(f"{model_class.__name__} with id {instance_id} not found.",extra=self.logger_extra)

        except Exception as e:
            logger.error(
                f"Failed to update ETL status for {model_class.__name__} {instance_id}: {e}",
                extra=self.logger_extra,
            )
