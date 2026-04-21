import os
import shutil
from typing import Tuple


from emailbot.config.settings import logger
from rag.ETL_Pipeline.init import (
    KBFiles,
    KBText,
    KBWebsite,
    KBQuestions,
    KBQuestionAnswer,
    ETLStatus,
    ETLTracker,
    ETLRecordType,
)
import re
from typing import List, Dict
import asyncio
from pathlib import Path
from google.genai import types
from google import genai
from urllib.parse import urlparse, unquote
from crawl4ai import AsyncWebCrawler
from crawl4ai.async_configs import CrawlerRunConfig
from langchain_text_splitters import (
    MarkdownTextSplitter,
    RecursiveCharacterTextSplitter,
)
from .embeddings import Embeddings
from qdrant_client.models import PointStruct
from rag.config.constants import (
    MODEL_NAME,
    DEVICE,
    QDRANT_UPSERTING_BATCH_SIZE,
)
from concurrent.futures import ThreadPoolExecutor, as_completed
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling_core.types.doc import ImageRefMode, PictureItem, TableItem
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import (
    PdfPipelineOptions,
    RapidOcrOptions,
    TesseractOcrOptions,
    EasyOcrOptions,
)
import sys
import platform
import subprocess
import uuid
from datetime import datetime
import requests
from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
from crawl4ai.deep_crawling import BFSDeepCrawlStrategy
from crawl4ai.content_scraping_strategy import LXMLWebScrapingStrategy
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
from crawl4ai.async_configs import CacheMode
from docling.datamodel.settings import settings
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.core.credentials import AzureKeyCredential
from azure.ai.documentintelligence.models import (
    AnalyzeDocumentRequest,
    DocumentContentFormat,
)
from emailbot.config.settings import Settings
Settings()

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())


class Extractor:
    gemini_client = None
    doc_converter = None

    def __init__(self, etl_pipeline):
        self.etl_pipeline = etl_pipeline
        self.logger_extra = etl_pipeline.logger_extra
        try:
            self.embedder = Embeddings(
                logger_extra=etl_pipeline.logger_extra, q_client=etl_pipeline.Q_client
            )
        except Exception as e:
            logger.error(
                f"Failed to initialize Embeddings in Extractor: {e}",
                extra=self.logger_extra,
            )
            raise
        self.doc_converter = DocumentConverter()

    def remove_id_from_data_ids(self, id: str) -> bool:
        if id in self.etl_pipeline.data_ids:
            self.etl_pipeline.data_ids.remove(id)
            return True
        return False

    def remove_id_from_processed_ids(self, id: str) -> bool:
        if id in self.etl_pipeline.processed_ids:
            self.etl_pipeline.processed_ids.remove(id)
            return True
        return False

    def convert_doc_to_markdown(self, input_path: Path):
        try:
            if self.doc_converter is None:
                self.doc_converter = DocumentConverter()
            markdown_text = self.doc_converter.convert(str(input_path))
            return True, markdown_text
        except Exception as e:
            error_message = f"Error converting document to markdown: {e}"
            logger.error(error_message, extra=self.logger_extra)
            return False, error_message

    def convert_to_pdf(
        self, input_file: Path, converted_files: Path
    ) -> Tuple[bool, Path | str]:
        try:
            converted_files.mkdir(parents=True, exist_ok=True)

            system_name = platform.system()
            logger.info(
                f"Converting file on {system_name} system", extra=self.logger_extra
            )

            if system_name == "Windows":
                if input_file.suffix.lower() == ".docx":
                    from docx2pdf import convert as docx_to_pdf_converter

                    docx_to_pdf_converter(str(input_file), str(converted_files))
                elif input_file.suffix.lower() == ".pptx":
                    from pptxtopdf import convert as pptx_to_pdf_converter

                    pptx_to_pdf_converter(str(input_file), str(converted_files))
                else:
                    msg = f"Unsupported file format for Windows conversion: {input_file.suffix}"
                    logger.error(msg, extra=self.logger_extra)
                    return False, msg

                pdf_path = converted_files / f"{input_file.stem}.pdf"

                if not pdf_path.exists():
                    msg = f"Expected PDF not found after Windows conversion: {pdf_path}"
                    logger.error(msg, extra=self.logger_extra)
                    return False, msg

                return True, pdf_path
            else:
                cmd = [
                    "libreoffice",
                    "--headless",
                    "--nologo",
                    "--nofirststartwizard",
                    "--convert-to",
                    "pdf",
                    "--outdir",
                    str(converted_files),
                    str(input_file),
                ]

                result = subprocess.run(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
                )

                logger.info(
                    f"LibreOffice stdout: {result.stdout}", extra=self.logger_extra
                )
                if result.stderr:
                    logger.info(
                        f"LibreOffice stderr: {result.stderr}", extra=self.logger_extra
                    )

                if result.returncode != 0:
                    error_message = (
                        f"LibreOffice failed to convert {input_file.name} "
                        f"(exit code {result.returncode}). "
                        f"Stdout: {result.stdout} Stderr: {result.stderr}"
                    )
                    logger.error(error_message, extra=self.logger_extra)
                    return False, error_message

                pdf_path = converted_files / f"{input_file.stem}.pdf"
                if not pdf_path.exists():
                    error_message = (
                        f"LibreOffice reported success but PDF not found at: {pdf_path}"
                    )
                    logger.error(error_message, extra=self.logger_extra)
                    return False, error_message
                return True, pdf_path

        except Exception as e:
            error_message = f"Error converting file to PDF: {e}"
            logger.error(error_message, extra=self.logger_extra)
            return False, error_message

    def _stable_point_id(self, doc_id: str, chunk_index: int) -> str:
        return f"{doc_id}_{chunk_index}"

    def markdown_converter_upserting(
        self, markdown_text: str, source: str, kb_id: str, doc_id: str, type: str
    ) -> tuple[bool, str]:
        if type == "pair":
            splitter = RecursiveCharacterTextSplitter(
                separators=["##"], chunk_size=100, chunk_overlap=10
            )

        else:
            splitter = MarkdownTextSplitter(chunk_size=1000, chunk_overlap=100)

        sub_chunks = splitter.split_text(markdown_text)

        try:
            dense_embeddings = self.embedder.get_dense_embeddings(sub_chunks)

            points = []

            for idx, (dense_embedding, doc) in enumerate(
                zip(dense_embeddings, sub_chunks)
            ):
                current_timestamp = int(datetime.now().timestamp())
                point = PointStruct(
                    id=str(
                        uuid.uuid5(
                            uuid.NAMESPACE_DNS,
                            f"{kb_id}_{doc_id}_{idx}_{current_timestamp}",
                        )
                    ),
                    vector={MODEL_NAME: dense_embedding},
                    payload={
                        "document": doc,
                        "source": str(source),
                        "doc_id": doc_id,
                        "chunk_index": idx,  # Store original index for reference
                        "tenant_id": self.etl_pipeline.tenant_id,
                        "kb_id": kb_id,
                    },
                )
                # logger.info(f"Point ID: {point.id}, Payload keys: {list(point.payload.keys())}", extra=self.logger_extra)

                points.append(point)

            for i in range(0, len(points), QDRANT_UPSERTING_BATCH_SIZE):
                batch_points = points[i : i + QDRANT_UPSERTING_BATCH_SIZE]
                operation_info = self.etl_pipeline.Q_client.upsert(
                    collection_name=self.etl_pipeline.Q_manager.collection_name,
                    points=batch_points,
                )
                logger.info(
                    f"Upserted batch of {len(batch_points)} points: {operation_info}",
                    extra=self.logger_extra,
                )

            message = f"✅ Stored {len(sub_chunks)} chunks from {source} into collection '{self.etl_pipeline.Q_manager.collection_name}'"
            logger.info(message, extra=self.logger_extra)
            return True, message

        except Exception as e:
            error_message = f"Error processing markdown : {str(e)}"
            logger.error(f"{error_message}", extra=self.logger_extra)
            return False, error_message

    def process_text_file(self, file_entry: dict) -> Tuple[bool, str]:
        try:
            file_id = file_entry.get("id")
            file_url = file_entry.get("file")

            if not file_url:
                self.etl_pipeline.update_etl_status(
                    model_class=KBFiles,
                    instance_id=file_id,
                    status=ETLStatus.FAILED,
                    message="Text file has no file path/URL, skipping",
                )
                warning_message = f"Text file {file_id} has no file path/URL, skipping"
                logger.warning(warning_message, extra=self.logger_extra)
                self.remove_id_from_data_ids(file_id)
                return False, warning_message

            # Download and read the text file

            response = requests.get(file_url)
            response.raise_for_status()
            text_content = response.text

            # Process the text content as markdown
            title = file_entry.get("title", f"File_{file_id}")
            final_str = f"## {title}\n\n{text_content}"

            success, message = self.markdown_converter_upserting(
                markdown_text=final_str,
                source=title,
                kb_id=self.etl_pipeline.kb_id,
                doc_id=file_id,
                type="bulk",
            )

            if success:
                msg = f"Successfully processed text file: {title} (ID: {file_id})"
                logger.info(msg, extra=self.logger_extra)
                return True, msg
            else:
                msg = f"Failed to process text file: {title} (ID: {file_id}): {message}"
                logger.error(msg, extra=self.logger_extra)
                return False, msg

        except Exception as e:
            msg = f"Error processing text file entry {file_entry.get('id', 'unknown')}: {e}"
            logger.error(msg, extra=self.logger_extra)
            return False, msg

    def get_image_summary(self, image_path: Path) -> Tuple[bool, str, str, str]:
        try:
            if self.gemini_client is None:
                # GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
                GEMINI_API_KEY = Settings().gemini_api_key
                self.gemini_client = genai.Client(api_key=GEMINI_API_KEY)
            prompt = """
            You are an expert AI assistant analyzing technical images. Your task is to generate a concise, structured description focused only on relevant content, suitable for retrieval-augmented question answering.
            - If the image contains a diagram, chart, table, flowchart, or graph:
            - Briefly explain each element's function and layout (e.g., axes and relationships in a graph, rows/columns in a table, steps and relations in a flowchart), focusing only on the main figure and ignoring unrelated regions.
            - Do not include details about color, shape, or artistic attributes.
            - Avoid unnecessary detail: Only describe what is essential to understand the figure or answer related technical queries.
            - If the image contains visible text (via OCR or in the image itself):
            - Extract and list all meaningful, readable text as a structured list or block (preserve table or bullet formats if present).
            - Do not add explanations or paraphrasing.
            - If multiple diagrams or figures are present, only describe the most relevant figure, according to the likely prompt or context.
            - If the image is not a technical figure, chart, table, or graph, reply: "No relevant technical content detected."
            """

            with open(image_path, "rb") as img_file:
                image_data = img_file.read()
                response = self.gemini_client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=[
                        types.Part.from_bytes(data=image_data, mime_type="image/jpeg"),
                        prompt,
                    ],
                )
            summary = (
                response.text.strip() if hasattr(response, "text") else str(response)
            )
            return True, "Image processed successfully", summary, image_path.name
        except Exception as e:
            error_message = f"Gemini Vision Error for {image_path.name}: {e}"
            logger.error(error_message, extra=self.logger_extra)
            return False, error_message, "", image_path.name

    def process_image_file(self, image_path: Path, file_id: str) -> Tuple[bool, str]:
        try:
            logger.info("Processing image file", extra=self.logger_extra)
            base_path = Path(f"Results/{self.etl_pipeline.tenant_id}/output")
            base_path.mkdir(parents=True, exist_ok=True)

            target_path = base_path / image_path.name
            if image_path != target_path:
                shutil.copy(image_path, target_path)
                logger.info(f"Copied image to {target_path}", extra=self.logger_extra)

            success, message, summary, img_name = self.get_image_summary(target_path)
            if success:
                md_path = base_path / f"{image_path.stem}-summary.md"
                with open(md_path, "w", encoding="utf-8") as f:
                    f.write(f"## {image_path.name}\n\n")
                    f.write(f"![{image_path.stem}]({target_path})\n\n")
                    f.write(f"> **Image Summary:** {summary}\n")

                status, msg = self.markdown_converter_upserting(
                    markdown_text=summary,
                    source=image_path.name,
                    kb_id=self.etl_pipeline.kb_id,
                    doc_id=file_id,
                    type="bulk",
                )

                os.remove(target_path)
                return status, msg
            else:
                err_message = (
                    f"Failed to get image summary for {image_path.name}: {message}"
                )
                logger.error(err_message, extra=self.logger_extra)
                return False, err_message
        except Exception as e:
            error_message = f"Error processing image file {image_path.name}: {e}"
            logger.error(error_message, extra=self.logger_extra)
            return False, error_message

    def process_document_file(
        self, input_url: str
    ) -> tuple[bool, str, str | None | Path]:
        try:
            poller = self.doc_client.begin_analyze_document(
                model_id="prebuilt-layout",
                body=AnalyzeDocumentRequest(url_source=input_url),
                output_content_format=DocumentContentFormat.MARKDOWN,
            )
            result = poller.result()
            markdown_content = result.content
            return True, "success", markdown_content

        except Exception as e:
            error_message = f"Error processing document file: {e}"
            logger.exception(error_message, extra=self.logger_extra)
            return False, error_message, None

    def process_file_entry(self, input_path: str, doc_id: str) -> tuple[bool, str]:
        temp_file = None
        try:
            if input_path.startswith("http://") or input_path.startswith("https://"):

                sanitized_url = (
                    input_path.replace("://", "###")
                    .replace("//", "/")
                    .replace("###", "://")
                )

                response = requests.get(sanitized_url)
                response.raise_for_status()

                parsed_url = urlparse(sanitized_url)
                original_name = Path(unquote(parsed_url.path)).name.strip()

                if not original_name:
                    original_name = f"file_{uuid.uuid4().hex}"

                ext = Path(original_name).suffix.lower()

                TEMP_DIR = Path.cwd() / "temp_files"
                TEMP_DIR.mkdir(parents=True, exist_ok=True)

                temp_file = TEMP_DIR / f"{uuid.uuid4().hex}{ext}"
                logger.info(
                    f"Generated temporary file path: {temp_file}",
                    extra=self.logger_extra,
                )

                with open(temp_file, "wb") as f:
                    f.write(response.content)

                file_url = input_path
                input_path = temp_file

                ext = Path(input_path).suffix.lower()

                if ext == ".md":
                    logger.info(
                        f"Detected markdown file: {input_path.name}",
                        extra=self.logger_extra,
                    )
                    with open(input_path, "r", encoding="utf-8") as f:
                        markdown_text = f.read()

                    success, message = self.markdown_converter_upserting(
                        markdown_text=markdown_text,
                        source=input_path.name,
                        kb_id=self.etl_pipeline.kb_id,
                        doc_id=doc_id,
                        type="pair",
                    )
                    return success, message

                elif ext in [".png", ".jpg", ".jpeg", ".svg"]:
                    logger.info(f"Detected image file: {input_path.name}")
                    success, msg = self.process_image_file(input_path, doc_id)
                    return success, msg

                success, msg, md_err = self.process_document_file(file_url)
                if success:
                    success, message = self.markdown_converter_upserting(
                        markdown_text=md_err,
                        source=f"{input_path.name}",
                        kb_id=self.etl_pipeline.kb_id,
                        doc_id=doc_id,
                        type="bulk",
                    )

                    logger.info(f"Markdown upserted: ", extra=self.logger_extra)
                    return success, message
                else:
                    return False, msg
            else:
                error_message = f"Input path is not a valid URL: {input_path}"
                logger.error(error_message, extra=self.logger_extra)
                return False, error_message
        except Exception as e:
            error_message = f"Error processing file {input_path}: {e}"
            logger.exception(error_message, extra=self.logger_extra)
            return False, error_message
        finally:
            if temp_file and temp_file.exists():
                try:
                    temp_file.unlink()
                    logger.info(
                        f"Deleted temporary file: {temp_file}", extra=self.logger_extra
                    )
                except Exception as e:
                    logger.warning(
                        f"Could not delete temporary file {temp_file}: {e}",
                        extra=self.logger_extra,
                    )

    def process_all_files_dict(self) -> bool:
        files = self.etl_pipeline.data.get("files", [])
        processed_count = 0
        overall_success = True

        try:
            for file_entry in files:
                try:
                    file_id = file_entry.get("id")

                    self.etl_pipeline.update_etl_status(
                        model_class=KBFiles,
                        instance_id=file_id,
                        status=ETLStatus.IN_PROGRESS,
                        message="Processing file entry",
                    )
                    logger.info(
                        f"Processing file entry: ID={file_id}",
                        extra=self.etl_pipeline.logger_extra,
                    )

                    if file_entry.get("is_deleted", False):
                        success, message = (
                            self.etl_pipeline.Q_manager.delete_from_qdrant(
                                doc_id=file_id
                            )
                        )
                        if success:
                            self.etl_pipeline.update_etl_status(
                                model_class=KBFiles,
                                instance_id=file_id,
                                status=ETLStatus.COMPLETED,
                                message=message,
                            )
                            logger.info(
                                f"Deleted file data for ID: {file_id}",
                                extra=self.logger_extra,
                            )
                            self.remove_id_from_data_ids(file_id)
                        else:
                            self.etl_pipeline.update_etl_status(
                                model_class=KBFiles,
                                instance_id=file_id,
                                status=ETLStatus.FAILED,
                                message=message,
                            )
                            overall_success = False
                            logger.error(
                                f"Failed to delete file data for ID: {file_id}: {message}",
                                extra=self.logger_extra,
                            )
                            self.remove_id_from_data_ids(file_id)
                        continue

                    # Process new or updated file
                    if (
                        file_id in self.etl_pipeline.data_ids
                        and file_id not in self.etl_pipeline.processed_ids
                    ):
                        file_url = file_entry.get("file")

                        if not file_url:
                            msg = f"File {file_id} has no file path/URL, skipping"
                            self.etl_pipeline.update_etl_status(
                                model_class=KBFiles,
                                instance_id=file_id,
                                status=ETLStatus.FAILED,
                                message=msg,
                            )
                            logger.warning(msg, extra=self.etl_pipeline.logger_extra)

                            self.remove_id_from_data_ids(file_id)
                            self.remove_id_from_processed_ids(file_id)
                            continue

                        logger.info(
                            f"Processing file: {file_url}", extra=self.logger_extra
                        )

                        # Handle .txt files specially
                        if str(file_url).lower().endswith(".txt"):
                            success, message = self.process_text_file(file_entry)
                            if success:
                                processed_count += 1
                                self.etl_pipeline.update_etl_status(
                                    model_class=KBFiles,
                                    instance_id=file_id,
                                    status=ETLStatus.COMPLETED,
                                    message=message,
                                )
                                self.remove_id_from_data_ids(file_id)
                            else:
                                self.etl_pipeline.update_etl_status(
                                    model_class=KBFiles,
                                    instance_id=file_id,
                                    status=ETLStatus.FAILED,
                                    message=message,
                                )
                                overall_success = False
                        else:
                            try:
                                success, msg = self.process_file_entry(
                                    input_path=file_url,
                                    doc_id=file_id,
                                )
                                if not success:
                                    self.etl_pipeline.update_etl_status(
                                        model_class=KBFiles,
                                        instance_id=file_id,
                                        status=ETLStatus.FAILED,
                                        message=msg,
                                    )
                                    overall_success = False
                                else:
                                    self.etl_pipeline.update_etl_status(
                                        model_class=KBFiles,
                                        instance_id=file_id,
                                        status=ETLStatus.COMPLETED,
                                        message=msg,
                                    )
                                    logger.info(
                                        f"Successfully processed file: {file_url}"
                                    )
                                    processed_count += 1
                            except Exception as e:
                                self.etl_pipeline.update_etl_status(
                                    model_class=KBFiles,
                                    instance_id=file_id,
                                    status=ETLStatus.FAILED,
                                    message=f"Error processing file {file_url}: {e}",
                                )
                                overall_success = False
                                logger.error(f"Error processing file {file_url}: {e}")

                            self.remove_id_from_data_ids(file_id)

                    # Skip unchanged file
                    elif (
                        file_id in self.etl_pipeline.data_ids
                        and file_id in self.etl_pipeline.processed_ids
                    ):
                        self.remove_id_from_data_ids(file_id)
                        self.remove_id_from_processed_ids(file_id)
                        self.etl_pipeline.update_etl_status(
                            model_class=KBFiles,
                            instance_id=file_id,
                            status=ETLStatus.COMPLETED,
                            message="File unchanged, skipping",
                        )
                        logger.info(f"File {file_id} unchanged, skipping")

                except Exception as e:
                    _ = f"Error processing file entry {file_entry.get('id', 'unknown')} : {e}"
                    logger.error(_, extra=self.logger_extra)
                    if file_entry.get("id", None):
                        self.etl_pipeline.update_etl_status(
                            model_class=KBFiles,
                            instance_id=file_entry.get("id"),
                            status=ETLStatus.FAILED,
                            message=_,
                        )
                    overall_success = False
                    continue

            logger.info(f"Processed {processed_count} file entries")
            return overall_success

        except Exception as e:
            logger.error(f"Critical error in process_files: {e}")
            overall_success = False
            return overall_success

    def process_all_texts_dict(self) -> bool:
        overall_success = True
        try:

            texts_json = self.etl_pipeline.data.get("texts", [])

            for text in texts_json:
                try:
                    text_id = text.get("id", "")
                    if not text_id:
                        logger.warning(
                            "Text entry has no ID, skipping", extra=self.logger_extra
                        )
                        continue

                    self.etl_pipeline.update_etl_status(
                        model_class=KBText,
                        instance_id=text_id,
                        status=ETLStatus.IN_PROGRESS,
                        message="Processing text entry",
                    )

                    logger.info(
                        f"Processing text entry: ID={text_id}", extra=self.logger_extra
                    )

                    if text.get("is_deleted", False):
                        success, message = (
                            self.etl_pipeline.Q_manager.delete_from_qdrant(
                                doc_id=text_id
                            )
                        )
                        if success:
                            self.etl_pipeline.update_etl_status(
                                model_class=KBText,
                                instance_id=text_id,
                                status=ETLStatus.COMPLETED,
                                message=message,
                            )
                            logger.info(
                                f"Deleted text data for ID: {text_id}",
                                extra=self.logger_extra,
                            )
                            self.remove_id_from_data_ids(text_id)
                        else:
                            self.etl_pipeline.update_etl_status(
                                model_class=KBText,
                                instance_id=text_id,
                                status=ETLStatus.FAILED,
                                message=message,
                            )
                            overall_success = False
                            logger.error(
                                f"Failed to delete text data for ID: {text_id}: {message}",
                                extra=self.logger_extra,
                            )
                            self.remove_id_from_data_ids(text_id)
                        continue

                    if (
                        text_id in self.etl_pipeline.data_ids
                        and text_id not in self.etl_pipeline.processed_ids
                    ):
                        description = text.get("description", "")
                        title = text.get("title", "")

                        if not description or not title:
                            warning_message = (
                                f"Text {text_id} missing title or description, skipping"
                            )
                            logger.warning(warning_message, extra=self.logger_extra)
                            self.etl_pipeline.update_etl_status(
                                model_class=KBText,
                                instance_id=text_id,
                                status=ETLStatus.FAILED,
                                message=warning_message,
                            )
                            self.remove_id_from_data_ids(text_id)
                            overall_success = False
                            continue

                        final_str = f"## {title}\n\n{description}"

                        success, message = self.markdown_converter_upserting(
                            markdown_text=final_str,
                            source=title,
                            kb_id=self.etl_pipeline.kb_id,
                            doc_id=text_id,
                            type="pair",
                        )

                        if success:
                            msg = (
                                f"Successfully processed text: {title} (ID: {text_id})"
                            )
                            self.etl_pipeline.update_etl_status(
                                model_class=KBText,
                                instance_id=text_id,
                                status=ETLStatus.COMPLETED,
                                message=msg,
                            )
                            logger.info(msg, extra=self.logger_extra)
                        else:
                            msg = f"Failed to process text: {title} (ID: {text_id}): {message}"
                            self.etl_pipeline.update_etl_status(
                                model_class=KBText,
                                instance_id=text_id,
                                status=ETLStatus.FAILED,
                                message=msg,
                            )
                            logger.error(msg, extra=self.logger_extra)
                            overall_success = False

                        self.remove_id_from_data_ids(text_id)

                    elif (
                        text_id in self.etl_pipeline.data_ids
                        and text_id in self.etl_pipeline.processed_ids
                    ):
                        self.remove_id_from_data_ids(text_id)
                        self.remove_id_from_processed_ids(text_id)
                        self.etl_pipeline.update_etl_status(
                            model_class=KBText,
                            instance_id=text_id,
                            status=ETLStatus.COMPLETED,
                            message="Text unchanged, skipping",
                        )
                        logger.info(
                            f"Text {text_id} unchanged, skipping",
                            extra=self.logger_extra,
                        )
                except Exception as e:
                    error_message = (
                        f"Error processing text entry {text.get('id', 'unknown')}: {e}"
                    )
                    logger.error(error_message, extra=self.logger_extra)
                    if text.get("id", None):
                        self.etl_pipeline.update_etl_status(
                            model_class=KBText,
                            instance_id=text.get("id"),
                            status=ETLStatus.FAILED,
                            message=error_message,
                        )
                    overall_success = False
                    continue
        except Exception as e:
            logger.error(
                f"Critical error in process_texts: {e}", extra=self.logger_extra
            )
            overall_success = False
        return overall_success

    async def process_website_url(self, url: str, doc_id: str) -> Tuple[bool, str]:
        try:
            logger.info(f"Starting processing for url: {url}", extra=self.logger_extra)
            md_generator = DefaultMarkdownGenerator(
                options={
                    "ignore_links": True,
                    "ignore_images": True,
                    "escape_html": True,
                    "protect_links": True,
                },
            )
            config = CrawlerRunConfig(
                deep_crawl_strategy=BFSDeepCrawlStrategy(
                    max_depth=2,
                ),
                prettiify=True,
                scraping_strategy=LXMLWebScrapingStrategy(),
                verbose=True,
                cache_mode=CacheMode.BYPASS,
                markdown_generator=md_generator,
            )
            async with AsyncWebCrawler() as crawler:
                result = await crawler.arun(url=url, config=config)
                final_result = ""
                for page_content in result:
                    final_result += (
                        page_content.markdown
                        if page_content.markdown
                        else page_content.text
                    )

                success, message = self.markdown_converter_upserting(
                    markdown_text=final_result,
                    source=url,
                    kb_id=self.etl_pipeline.kb_id,
                    doc_id=doc_id,
                    type="bulk",
                )
                if success:
                    logger.info(
                        f"Successfully processed website URL: {url}",
                        extra=self.logger_extra,
                    )
                    return True, f"Successfully processed website URL: {url}"
                else:
                    logger.error(
                        f"Failed to process website URL: {url}: {message}",
                        extra=self.logger_extra,
                    )
                    return False, f"Failed to process website URL: {url}: {message}"
        except Exception as e:
            error_message = f"Error processing website URL {url}: {e}"
            logger.error(error_message, extra=self.logger_extra)
            return False, error_message

    def process_all_website_dict(self) -> bool:
        websites_json = self.etl_pipeline.data.get("websites", [])
        overall_success = True
        for website_entry in websites_json:
            website_id = None
            try:
                website_id = website_entry.get("id")
                website_url = website_entry.get("url")

                if not website_url:
                    self.etl_pipeline.update_etl_status(
                        model_class=KBWebsite,
                        instance_id=website_id,
                        status=ETLStatus.FAILED,
                        message="Website entry has no URL, skipping",
                    )
                    logger.warning(
                        f"Website entry {website_id} has no URL, skipping",
                        extra=self.logger_extra,
                    )
                    self.remove_id_from_data_ids(website_id)
                    overall_success = False
                    continue

                self.etl_pipeline.update_etl_status(
                    model_class=KBWebsite,
                    instance_id=website_id,
                    status=ETLStatus.IN_PROGRESS,
                    message="Processing website entry",
                )

                logger.info(
                    f"Processing website entry: ID={website_id}, URL={website_url}",
                    extra=self.logger_extra,
                )
                if website_entry.get("is_deleted", False):
                    success, message = self.etl_pipeline.Q_manager.delete_from_qdrant(
                        doc_id=website_id
                    )
                    if success:
                        self.etl_pipeline.update_etl_status(
                            model_class=KBWebsite,
                            instance_id=website_id,
                            status=ETLStatus.COMPLETED,
                            message=message,
                        )
                        logger.info(
                            f"Deleted website data for ID: {website_id}",
                            extra=self.logger_extra,
                        )
                        self.remove_id_from_data_ids(website_id)
                    else:
                        self.etl_pipeline.update_etl_status(
                            model_class=KBWebsite,
                            instance_id=website_id,
                            status=ETLStatus.FAILED,
                            message=message,
                        )
                        overall_success = False
                        logger.error(
                            f"Failed to delete website data for ID: {website_id}: {message}",
                            extra=self.logger_extra,
                        )
                        self.remove_id_from_data_ids(website_id)
                    continue

                if (
                    website_id in self.etl_pipeline.data_ids
                    and website_id not in self.etl_pipeline.processed_ids
                ):

                    success, message = asyncio.run(
                        self.process_website_url(website_url, website_id)
                    )

                    if success:
                        msg = f"Successfully processed website URL: {website_url} (ID: {website_id})"
                        self.etl_pipeline.update_etl_status(
                            model_class=KBWebsite,
                            instance_id=website_id,
                            status=ETLStatus.COMPLETED,
                            message=msg,
                        )
                        logger.info(msg, extra=self.logger_extra)
                        self.remove_id_from_data_ids(website_id)
                        continue
                    else:
                        msg = f"Failed to process website URL: {website_url} (ID: {website_id}): {message}"
                        self.etl_pipeline.update_etl_status(
                            model_class=KBWebsite,
                            instance_id=website_id,
                            status=ETLStatus.FAILED,
                            message=msg,
                        )
                        logger.error(msg, extra=self.logger_extra)
                        overall_success = False
                        self.remove_id_from_data_ids(website_id)
                        continue

                elif (
                    website_id in self.etl_pipeline.data_ids
                    and website_id in self.etl_pipeline.processed_ids
                ):
                    self.remove_id_from_data_ids(website_id)
                    self.remove_id_from_processed_ids(website_id)
                    self.etl_pipeline.update_etl_status(
                        model_class=KBWebsite,
                        instance_id=website_id,
                        status=ETLStatus.COMPLETED,
                        message="Website unchanged, skipping",
                    )
                    logger.info(
                        f"Website {website_id} unchanged, skipping",
                        extra=self.logger_extra,
                    )

            except Exception as e:
                if website_id is not None:
                    self.etl_pipeline.update_etl_status(
                        model_class=KBWebsite,
                        instance_id=website_id,
                        status=ETLStatus.FAILED,
                        message=f"Error processing website entry: {e}",
                    )
                msg = f"Error processing website entry {website_entry.get('id', 'unknown')}: {e}"
                logger.error(msg, extra=self.logger_extra)
                overall_success = False
                continue
        return overall_success

    def process_all_questions_answers(self) -> bool:
        overall_success = True
        try:
            qa_json = self.etl_pipeline.data.get("question_answers", [])

            for qa_entry in qa_json:
                inner_overall_success = True
                qa_id = None
                try:
                    qa_id = qa_entry.get("id")
                    title = qa_entry.get("title", "")
                    questions = qa_entry.get("questions", [])
                    answer = qa_entry.get("answer", "")

                    self.etl_pipeline.update_etl_status(
                        model_class=KBQuestionAnswer,
                        instance_id=qa_id,
                        status=ETLStatus.IN_PROGRESS,
                        message="Processing question-answer entry",
                    )

                    logger.info(
                        f"Processing question-answer entry: ID={qa_id}",
                        extra=self.logger_extra,
                    )

                    if qa_entry.get("is_deleted", False):
                        for q in questions:
                            q_id = q.get("id")
                            self.etl_pipeline.update_etl_status(
                                model_class=KBQuestions,
                                instance_id=q_id,
                                status=ETLStatus.IN_PROGRESS,
                                message="Deleting question as part of QA deletion",
                            )

                            success, message = (
                                self.etl_pipeline.Q_manager.delete_from_qdrant(
                                    kb_id=self.etl_pipeline.kb_id, doc_id=q_id
                                )
                            )
                            if success:
                                self.etl_pipeline.update_etl_status(
                                    model_class=KBQuestions,
                                    instance_id=q_id,
                                    status=ETLStatus.COMPLETED,
                                    message=message,
                                )
                                logger.info(
                                    f"Deleted question data for ID: {q_id}",
                                    extra=self.logger_extra,
                                )
                            else:
                                self.etl_pipeline.update_etl_status(
                                    model_class=KBQuestions,
                                    instance_id=q_id,
                                    status=ETLStatus.FAILED,
                                    message=message,
                                )
                                inner_overall_success = False
                                logger.error(
                                    f"Failed to delete question data for ID: {q_id}: {message}",
                                    extra=self.logger_extra,
                                )
                            self.remove_id_from_data_ids(q_id)
                        # Now delete the main QA entry

                        self.etl_pipeline.update_etl_status(
                            model_class=KBQuestionAnswer,
                            instance_id=qa_id,
                            status=ETLStatus.COMPLETED,
                            message="Deleted question-answer entry",
                        )
                        continue

                    for q in questions:
                        q_id = q.get("id")
                        self.etl_pipeline.update_etl_status(
                            model_class=KBQuestions,
                            instance_id=q_id,
                            status=ETLStatus.IN_PROGRESS,
                            message="Question part of QA processing",
                        )
                        if (
                            q_id in self.etl_pipeline.data_ids
                            and q_id not in self.etl_pipeline.processed_ids
                        ):
                            try:
                                q_quest = q.get("question", "")
                                markdown_content = f"## {title} \n\nQuestion: {q_quest}\n\nAnswer: {answer}"
                                success, message = self.markdown_converter_upserting(
                                    markdown_text=markdown_content,
                                    source=title,
                                    kb_id=self.etl_pipeline.kb_id,
                                    doc_id=q_id,
                                    type="pair",
                                )

                                if success:
                                    msg = f"Successfully processed question: {q_quest} (ID: {q_id})"
                                    self.etl_pipeline.update_etl_status(
                                        model_class=KBQuestions,
                                        instance_id=q_id,
                                        status=ETLStatus.COMPLETED,
                                        message=msg,
                                    )
                                else:
                                    msg = f"Failed to process question: {q_quest} (ID: {q_id})"
                                    self.etl_pipeline.update_etl_status(
                                        model_class=KBQuestions,
                                        instance_id=q_id,
                                        status=ETLStatus.FAILED,
                                        message=msg,
                                    )
                                    inner_overall_success = False
                            except Exception as e:
                                error_message = f"Error processing question {q_id}: {e}"
                                logger.error(error_message, extra=self.logger_extra)

                                self.etl_pipeline.update_etl_status(
                                    model_class=KBQuestions,
                                    instance_id=q_id,
                                    status=ETLStatus.FAILED,
                                    message=error_message,
                                )
                                inner_overall_success = False
                                continue
                            self.remove_id_from_data_ids(q_id)

                        elif (
                            q_id in self.etl_pipeline.data_ids
                            and q_id in self.etl_pipeline.processed_ids
                        ):
                            self.remove_id_from_processed_ids(q_id)
                            self.remove_id_from_data_ids(q_id)
                            self.etl_pipeline.update_etl_status(
                                model_class=KBQuestions,
                                instance_id=q_id,
                                status=ETLStatus.COMPLETED,
                                message="Question unchanged, skipping",
                            )
                            logger.info(
                                f"Question {q_id} unchanged, skipping",
                                extra=self.logger_extra,
                            )

                    self.etl_pipeline.update_etl_status(
                        model_class=KBQuestionAnswer,
                        instance_id=qa_id,
                        status=ETLStatus.COMPLETED,
                        message="Successfully processed question-answer entry",
                    )

                except Exception as e:
                    error_message = f"Error processing question-answer entry {qa_entry.get('id', 'unknown')}: {e}"
                    logger.error(error_message, extra=self.logger_extra)
                    if qa_entry.get("id", None):
                        self.etl_pipeline.update_etl_status(
                            model_class=KBQuestionAnswer,
                            instance_id=qa_entry.get("id"),
                            status=ETLStatus.FAILED,
                            message=error_message,
                        )
                    inner_overall_success = False

                if overall_success and not inner_overall_success:
                    overall_success = False

        except Exception as e:
            logger.error(
                f"Critical error in process_questions_answers: {e}",
                extra=self.logger_extra,
            )
            overall_success = False
        return overall_success
