import requests
from pathlib import Path
from urllib.parse import unquote, urlparse
import uuid
import platform
import subprocess
from google import genai
from google.genai import types
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling_core.types.doc import ImageRefMode, PictureItem, TableItem
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
from emailbot.config.settings import Settings
Settings()

gemini_client = None


def get_image_summary(image_path: Path) -> str:
    global gemini_client
    if gemini_client is None:
        print("Initializing Gemini client...")
        # gemini_client = genai.Client(api_key=os.getenv("GENAI_API_KEY"))
        gemini_client = genai.Client(api_key=Settings().gemini_api_key)
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
        response = gemini_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                types.Part.from_bytes(data=image_data, mime_type="image/jpeg"),
                prompt,
            ],
        )
    summary = response.text.strip() if hasattr(response, "text") else str(response)
    return summary


def proces_file_to_md(file_url: str, file_id: str = None) -> tuple[bool, str, str]:
    """Process a file from a given URL and convert its content to Markdown format."""
    files_to_delete = []
    file_path = None
    try:
        url = file_url.strip()

        # sanitized_url = file_url.replace("://", "###").replace("//","/").replace("###","://")

        parsed_url = urlparse(url)
        original_name = Path(unquote(parsed_url.path)).name.strip()

        if not original_name:
            original_name = f"file_{uuid.uuid4().hex}"

        ext = Path(original_name).suffix.lower()

        response = requests.get(url, stream=True, timeout=60)
        response.raise_for_status()

        if ext == ".txt":
            text = response.text
            title = f"File_{file_id}.txt" if file_id else "File.txt"
            md_content = f"# {title}\n\n{text}"
            return True, original_name, md_content
        elif ext == ".md":
            md_content = response.text
            return True, original_name, md_content

        else:

            temp_dir = Path.cwd() / "temp_files"
            temp_dir.mkdir(parents=True, exist_ok=True)

            file_path = temp_dir / f"{uuid.uuid4().hex}{ext}"

            # Save the downloaded file temporarily
            with open(file_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

            files_to_delete.append(file_path)

            pdf_path = None

            if ext in [".docx", ".pptx"]:
                temp_converted_dir = temp_dir / "converted_files"
                temp_converted_dir.mkdir(parents=True, exist_ok=True)

                system_name = platform.system()

                if system_name == "Windows":
                    if ext == ".docx":
                        from docx2pdf import convert as docx_to_pdf_converter

                        docx_to_pdf_converter(str(file_path), str(temp_converted_dir))
                    else:
                        from pptxtopdf import convert as pptx_to_pdf_converter

                        pptx_to_pdf_converter(str(file_path), str(temp_converted_dir))

                    pdf_path = temp_converted_dir / f"{file_path.stem}.pdf"
                    if not pdf_path.exists():
                        return False, "Error", "Conversion to PDF failed."
                else:
                    cmd = [
                        "libreoffice",
                        "--headless",
                        "--nologo",
                        "--nofirststartwizard",
                        "--convert-to",
                        "pdf",
                        "--outdir",
                        str(temp_converted_dir),
                        str(file_path),
                    ]

                    result = subprocess.run(
                        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
                    )

                    if result.stderr:
                        return (
                            False,
                            "Error",
                            f"Conversion to PDF failed: {result.stderr}",
                        )

                    if result.returncode != 0:
                        print(f"LibreOffice failed to convert {file_path.name}")
                        print(f"Stdout: {result.stdout}")
                        print(f"Stderr: {result.stderr}")
                        return False, "Error", "Conversion to PDF failed."

                    pdf_path = temp_converted_dir / f"{file_path.stem}.pdf"

                    if not pdf_path.exists():
                        return False, "Error", "Conversion to PDF failed."
            elif ext in [".png", ".jpg", ".jpeg", ".svg"]:
                image_path = file_path
                summary = get_image_summary(image_path)
                md_text = f"## {original_name}\n\n ![{image_path.stem}] \n\n > ** Image Summary:** \n\n {summary} \n\n"
                return True, image_path.name, md_text
            elif ext == ".pdf":
                pdf_path = file_path
            else:
                return False, "Error", f"Unsupported file extension: {ext}"

            pipeline_options = PdfPipelineOptions(
                images_scale=3.0,
                generate_page_images=True,
                generate_picture_images=True,
                generate_table_images=True,
                do_table_structure=True,
                do_cell_matching=True,
            )
            doc_converter = DocumentConverter(
                format_options={
                    InputFormat.PDF: PdfFormatOption(
                        pipeline_options=pipeline_options, device="cpu"
                    ),
                    InputFormat.CSV: PdfFormatOption(
                        pipeline_options=pipeline_options, device="cpu"
                    ),
                }
            )

            conv_res = doc_converter.convert(str(pdf_path))

            doc_filename = file_path.stem

            md_path = temp_dir / f"{doc_filename}-with-images.md"
            files_to_delete.append(md_path)
            conv_res.document.save_as_markdown(
                md_path, image_mode=ImageRefMode.REFERENCED
            )

            artifacts_dir = temp_dir / f"{doc_filename}-with-images_artifacts"
            image_paths = sorted(artifacts_dir.glob("*"))
            # files_to_delete.extend(image_paths)

            image_summaries = {}

            def process_and_store(idx, img_path):
                files_to_delete.append(img_path)
                return idx, get_image_summary(image_path=img_path)

            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = {
                    executor.submit(process_and_store, idx, path): idx
                    for idx, path in enumerate(image_paths)
                }
                for future in as_completed(futures):
                    idx, summary = future.result()
                    image_summaries[image_paths[idx].name] = summary

            with open(md_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            updated_lines = []
            for line in lines:
                if line.strip().startswith("![") and "](" in line:
                    img_path = line.split("](")[-1].replace(")", "").strip()
                    img_filename = os.path.basename(img_path)
                    summary = image_summaries.get(img_filename)
                    if summary:
                        updated_lines.append(
                            f"\n> **Image Summary:** {summary.strip()}\n\n"
                        )
                updated_lines.append(line)

            final_md_content = "".join(updated_lines)

            final_md_path = temp_dir / f"{doc_filename}-with-image-summaries.md"
            files_to_delete.append(final_md_path)

            with open(final_md_path, "w", encoding="utf-8") as f:
                f.writelines(final_md_content)

            files_to_delete.append(file_path)

            return True, original_name, final_md_content

    except Exception as e:
        return False, "Error", f"Error processing file: {e}"
    finally:
        for file in files_to_delete:
            try:
                if file.exists():
                    file.unlink()
            except Exception as e:
                print(f"Error deleting temporary file {file}: {e}")

        if file_path is not None and file_path.exists() and file_path.is_dir():
            file_path.rmdir()


if __name__ == "__main__":
    md = proces_file_to_md(
        file_url="https://prodapi.salesbot.cloud/media/2a6be9ab-a7b7-45ce-9432-2c4f9bb4accf/kb_files/DCR_nbMwB0i.pdf"
    )
    print(md)
