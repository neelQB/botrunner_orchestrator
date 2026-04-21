"""
Crawl Persona Agent - Website crawling and persona extraction.

This agent crawls a given Website URL and scrapes for info.
Post-Crawl, the info is cleaned and checked for total tokens.
Post-Clean the text is trimmed if exceeding max specified tokens.

The LLM is then called with the cleaned data to return an
autofilled version of BotPersona based on what data it was given.
"""
import re
import os
import asyncio
import litellm
import tempfile
import unicodedata
from opik import track, configure
from opik.integrations.litellm import track_completion
from agents import Agent, AgentOutputSchema
from agents import Runner, set_trace_processors
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig
from crawl4ai.deep_crawling import BFSDeepCrawlStrategy

from emailbot.utils.utils import get_consumption_info
from emailbot.config.settings import logger


from rag.ETL_Pipeline.process_json import ETLPipeLine
from emailbot.config import settings as _settings
_settings()
# configure(use_local=True)

# Patch litellm globally for Opik tracing
litellm.acompletion = track_completion()(litellm.acompletion)

# Set up tracing processors
set_trace_processors([OpikTracingProcessor()])


async def run_crawl_persona_agent(
    url: str,
    user_id: str,
    tenant_id: str ,
    max_depth: int = 2,
    max_pages: int = 50,
    max_tokens: int = 30000,
    max_products: int = 5,
):
    """
    Docstring for run_crawl_persona_agent

    :param url: Website URL to crawl
    :type url: str
    :param user_id: User ID for Knowledge Base ingestion
    :type user_id: str
    :param tenant_id: Tenant ID for VectorDB
    :type tenant_id: str
    :param max_depth: Maximum crawl depth
    :type max_depth: int
    :param max_pages: Maximum pages to crawl
    :type max_pages: int
    :param max_tokens: Maximum tokens for LLM
    :type max_tokens: int
    :param max_products: Maximum products to extract
    :type max_products: int
    """
    ### Defining CrawlerPersona agent
    crawl_persona_agent = Agent(
        name="crawl_persona_agent",
        instructions=crawl_persona_prompt(max_products=max_products),
        model=LitellmModel(model="gemini/gemini-3-flash-preview"),
        output_type=AgentOutputSchema(BotPersona, strict_json_schema=False),
    )

    ### Define Crawler Config
    config = CrawlerRunConfig(
        deep_crawl_strategy=BFSDeepCrawlStrategy(
            max_depth=max_depth,
            include_external=False,
            max_pages=max_pages,
        ),
        verbose=True,
        exclude_all_images=True,
        exclude_social_media_links=True,
        exclude_external_images=True,
    )
    logger.info("*" * 100)
    logger.info(
        f"Starting crawl for {url} with settings max_depth: {max_depth}, max_pages: {max_pages}, max_tokens: {max_tokens}, max_products: {max_products}"
    )
    logger.info("*" * 100)
    ### Satrt Crawling
    try:
        async with AsyncWebCrawler() as crawler:
            results = await crawler.arun(url, config=config)

            ### Extract clean content for LLM
            clean_pages = []
            for result in results:
                if result.success and result.markdown:
                    ### Skip media URLs after crawling
                    if is_media_url(result.url):
                        logger.info(f"⏭️  Skipped media: {result.url}")
                        continue

                    clean_content = {
                        "url": result.url,
                        "title": result.metadata.get("title", "N/A"),
                        "markdown": result.markdown,
                        "depth": result.metadata.get("depth", 0),
                    }
                    clean_pages.append(clean_content)
                    logger.info(f"✓ Cleaned: {result.url}")

            ### Combine pages
            combined_markdown = "\n\n---NEW PAGE---\n\n".join(
                [
                    f"# URL: {page['url']}\n# Title: {page['title']}\n\n{page['markdown']}"
                    for page in clean_pages
                ]
            )

            ### AGGRESSIVE CLEANING TO REDUCE TOKENS
            cleaned_content = clean_content_for_llm(combined_markdown)

            ### ENFORCE TOKEN LIMIT
            cleaned_content = enforce_token_limit(cleaned_content, max_tokens=max_tokens)

            #### Ingest in VectorDB
            try:
                # For Qdrant, we use the ETLPipeLine with a JSON structure
                payload = {
                    "texts": [
                        {
                            "id": f"crawl_{user_id}_{int(asyncio.get_event_loop().time())}",
                            "title": f"Crawled content for {url}",
                            "description": cleaned_content,
                        }
                    ]
                }

                # Prioritize passed tenant_id, then env, then fallback
                current_tenant = tenant_id 
                kb_id = user_id  # Using user_id as kb_id

                pipeline = ETLPipeLine(
                    json_value=payload,
                    etl_tracker_id=None,
                    tenant_id=current_tenant,
                    kb_id=kb_id,
                )
                success, message = pipeline.run_pipeline_from_json()
                if success:
                    logger.info(
                        f"Successfully ingested crawled content into Qdrant KB for user: {user_id}"
                    )
                else:
                    logger.error(f"Failed to ingest to Qdrant: {message}")

                logger.info("*" * 100)
            except Exception as e:
                logger.error(f"Error ingesting to KB: {e}")
                logger.info("*" * 100)

            ### Log token savings
            original_tokens = len(combined_markdown) // 4
            cleaned_tokens = len(cleaned_content) // 4
            reduction = (
                ((original_tokens - cleaned_tokens) / original_tokens) * 100
                if original_tokens > 0
                else 0
            )

            logger.info("*" * 100)
            logger.info(f"\n📊 Token Stats:")
            logger.info(f"   Original: {original_tokens:,} tokens")
            logger.info(f"   Cleaned:  {cleaned_tokens:,} tokens")
            logger.info(f"   Saved:    {reduction:.1f}%")
            if cleaned_tokens > max_tokens:
                logger.info(f"   ⚠️  Trimmed to: {max_tokens:,} tokens")
            logger.info("*" * 100)

            ### Send cleaned content to agent
            agent_result = await Runner.run(
                starting_agent=crawl_persona_agent, input=cleaned_content
            )
            logger.info("*" * 100)
            logger.info(f"Agent result: {agent_result}")
            logger.info("*" * 100)
            extracted = agent_result.final_output
            if hasattr(extracted, "model_dump"):
                extracted = extracted.model_dump()

            logger.info("*" * 100)
            logger.info(f"Extracted: {extracted}")
            logger.info("*" * 100)

            consumption_data = get_consumption_info(
                raw_responses=agent_result.raw_responses,
                agent_name="crawl_persona_agent",
                primary_model="gemini/gemini-3-flash-preview",
                tags=["crawl_persona"]
            )

            return {
                "pages_analyzed": len(clean_pages),
                "urls": [p["url"] for p in clean_pages],
                "bot_persona": extracted,
                "consumption_info": consumption_data
            }
    except Exception as e:
        logger.error(f"Critical error in run_crawl_persona_agent: {e}")
        logger.exception("Full traceback:")
        return {
            "error": str(e),
            "pages_analyzed": 0,
            "urls": [],
            "bot_persona": None
        }


### Check if URL is a media file
def is_media_url(url: str) -> bool:
    """Check if URL points to an image/video file"""
    media_extensions = [
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".bmp",
        ".svg",
        ".webp",
        ".ico",
        ".tiff",
        ".tif",
        ".jfif",
        ".pjpeg",
        ".pjp",
        ".avif",
        ".apng",
        ".mp4",
        ".avi",
        ".mov",
        ".wmv",
        ".flv",
        ".mkv",
        ".webm",
        ".m4v",
        ".mpg",
        ".mpeg",
        ".3gp",
        ".ogv",
        ".ts",
        ".m2ts",
        ".mp3",
        ".wav",
        ".ogg",
        ".m4a",
        ".aac",
        ".flac",
        ".wma",
    ]
    url_lower = url.lower()
    return any(url_lower.endswith(ext) for ext in media_extensions)


def clean_content_for_llm(text: str) -> str:
    """
    Aggressive cleaning to reduce token count while preserving meaning
    """

    ### 1. Remove emojis and special Unicode
    text = remove_emojis(text)

    ### 2. Remove image/video references from text
    text = remove_media_references(text)

    ### 3. Remove duplicate navigation menus
    text = remove_duplicate_navigation(text)

    ### 4. Remove markdown link URLs (keep text only)
    text = re.sub(r"\[(.*?)\]\([^\)]+\)", r"\1", text)

    ### 5. Remove repeated junk sections
    junk_patterns = [
        r"Follow us.*?(?=\n#|\n##|---NEW PAGE---|$)",
        r"Subscribe.*?Sign up for.*?(?=\n#|\n##|---NEW PAGE---|$)",
        r"© \w+ \d{4}.*?(?=\n#|\n##|---NEW PAGE---|$)",
        r"404.*?Page not Found.*?(?=\n#|\n##|---NEW PAGE---|$)",
    ]
    for pattern in junk_patterns:
        text = re.sub(pattern, "", text, flags=re.DOTALL | re.IGNORECASE)

    ### 6. Remove empty bullet points
    text = re.sub(r"^\s*\*\s*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\*\s*\[\s*\]\s*$", "", text, flags=re.MULTILINE)

    ### 7. Remove excessive newlines (keep max 2 consecutive)
    text = re.sub(r"\n{3,}", "\n\n", text)

    ### 8. Remove newline characters within sentences (optional - be careful)
    # This removes mid-sentence line breaks but keeps paragraph breaks
    # text = re.sub(r'(?<=[a-z,])\n(?=[a-z])', ' ', text)  # Uncomment if needed

    ### 9. Collapse multiple spaces and tabs
    text = re.sub(r" {2,}", " ", text)
    text = re.sub(r"\t+", " ", text)

    ### 10. Remove lines with only whitespace
    lines = [line.rstrip() for line in text.split("\n")]
    text = "\n".join(line for line in lines if line.strip())

    ### 11. Final cleanup
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"  +", " ", text)  # Remove double spaces again

    return text.strip()


### Enforce token limit
def enforce_token_limit(text: str, max_tokens: int) -> str:
    """
    Trim content to stay within token limit
    Approximation: 1 token ≈ 4 characters
    """
    ### Calculate current tokens (rough estimate)
    estimated_tokens = len(text) // 4

    if estimated_tokens <= max_tokens:
        return text  # Under limit, no trimming needed

    ### Calculate max characters for 30k tokens
    max_chars = max_tokens * 4

    ### Trim to max chars and find last complete sentence
    trimmed = text[:max_chars]

    ### Try to cut at last sentence boundary (period followed by space/newline)
    last_period = max(
        trimmed.rfind(". "),
        trimmed.rfind(".\n"),
        trimmed.rfind("!\n"),
        trimmed.rfind("?\n"),
    )

    if last_period > max_chars * 0.9:  # If we're close to the limit
        trimmed = trimmed[: last_period + 1]

    ### Add truncation notice
    trimmed += "\n\n[... Content truncated to fit 30k token limit ...]"
    logger.info(f"   ⚠️  Trimmed to: {max_tokens:,} tokens")

    return trimmed


def remove_media_references(text: str) -> str:
    """Remove ALL image and video references from markdown text"""

    ### 1. Remove markdown image syntax: ![alt](url)
    text = re.sub(r"!\[.*?\]\([^\)]+\)", "", text)

    ### 2. Remove standalone media URLs
    media_pattern = r"https?://[^\s]+\.(jpg|jpeg|png|gif|bmp|svg|webp|ico|tiff|mp4|avi|mov|wmv|flv|mkv|webm|m4v|mpg|mpeg|mp3|wav|ogg)[^\s]*"
    text = re.sub(media_pattern, "", text, flags=re.IGNORECASE)

    ### 3. Remove image/video title sections
    text = re.sub(
        r"# Title: [^\n]*\.(jpg|jpeg|png|gif|webp|mp4|avi|mov|svg|ico|bmp|tiff)[^\n]*\n?",
        "",
        text,
        flags=re.IGNORECASE,
    )

    ### 4. Remove media URL lines
    text = re.sub(
        r"# URL: [^\n]*\.(jpg|jpeg|png|gif|webp|mp4|avi|mov|svg|ico|bmp|tiff)[^\n]*\n?",
        "",
        text,
        flags=re.IGNORECASE,
    )

    ### 5. Remove empty page sections
    text = re.sub(r"---NEW PAGE---\s*---NEW PAGE---", "---NEW PAGE---", text)
    text = re.sub(r"---NEW PAGE---\s*$", "", text)

    return text


def remove_emojis(text: str) -> str:
    """Remove all emojis and special Unicode symbols"""
    return "".join(
        char for char in text if unicodedata.category(char)[0] not in ["S", "C"]
    )


def remove_duplicate_navigation(text: str) -> str:
    """Remove duplicate navigation menus (keeps only first occurrence)"""
    nav_patterns = [
        r"\* \[ Our Services \].*?\* \[ Contact \].*?(?=\n#)",
        r"X\s*\n\s*\* \[.*?\].*?\* \[.*?\].*?(?=\n#)",
    ]

    for pattern in nav_patterns:
        matches = list(re.finditer(pattern, text, re.DOTALL))
        if len(matches) > 1:
            for match in matches[1:]:
                text = text.replace(match.group(), "")

    return text