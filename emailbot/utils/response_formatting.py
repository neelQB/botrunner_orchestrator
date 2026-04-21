import re
import markdown
from markdownify import markdownify as md
from functools import lru_cache

# Pre-compile regex patterns once at module level
_RE_MULTI_BR = re.compile(r"(<br\s*/?>\s*){2,}", re.IGNORECASE)
_RE_NESTED_DIV = re.compile(
    r"^\s*<div>\s*(<div>.*</div>)\s*</div>\s*$", re.IGNORECASE | re.DOTALL
)
_RE_LINE_ENDINGS = re.compile(r"\r\n|\\n")
_OUTER_DIV_LEN = len("<div>")  # = 5

_MD_EXTENSIONS = [
    "tables",
    "fenced_code",
    "nl2br",
]  # Avoid re-allocating list on every call


def _cleanup_html(html: str) -> str:
    """
    Cleanup helper:
    - Collapse multiple <br> into one
    - Collapse nested <div> wrappers
    """
    if not html:
        return html

    html = _RE_MULTI_BR.sub("<br>", html)

    # Iteratively unwrap <div><div>...</div></div>
    while True:
        new_html = _RE_NESTED_DIV.sub(r"\1", html)
        if (
            new_html is html or new_html == html
        ):  # `is` check short-circuits when no match
            break
        html = new_html

    return html.strip()


def markdown_to_html_div(markdown_text: str) -> str:
    """
    Convert Markdown to HTML and wrap it in a single clean <div>.
    Also removes redundant <br> and nested divs.
    """
    if not markdown_text:
        return "<div></div>"

    # Normalize line endings in one pass
    text = _RE_LINE_ENDINGS.sub("\n", markdown_text)

    html = markdown.markdown(text, extensions=_MD_EXTENSIONS)
    html = _cleanup_html(html)

    return f"<div>{html}</div>"


def html_div_to_markdown(html_text: str) -> str:
    """
    Convert HTML back to Markdown with cleanup:
    - Removes nested <div>
    - Collapses multiple <br>
    """
    if not html_text:
        return ""

    text = _cleanup_html(html_text.strip())

    # Strip outer <div>...</div> without string copies via slicing bounds
    if text.startswith("<div>") and text.endswith("</div>"):
        text = text[_OUTER_DIV_LEN : -(_OUTER_DIV_LEN + 1)]  # [5:-6]

    return md(text, heading_style="ATX", bullets="-").strip()
