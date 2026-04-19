"""
Google Docs Tool — read and export document content.
Supports plain text extraction and structured paragraph reading.
"""

from typing import Any, Dict, Optional
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

from app.core.logging import get_logger

logger = get_logger(__name__)


def _docs_service(access_token: str):
    creds = Credentials(token=access_token)
    return build("docs", "v1", credentials=creds, cache_discovery=False)


def _extract_text_from_doc(doc: dict) -> str:
    """
    Recursively extract plain text from a Google Docs structural element.
    Google Docs API returns content as nested structural elements.
    """
    text_parts = []
    body = doc.get("body", {})

    for element in body.get("content", []):
        if "paragraph" in element:
            for para_element in element["paragraph"].get("elements", []):
                text_run = para_element.get("textRun", {})
                content = text_run.get("content", "")
                if content:
                    text_parts.append(content)

        elif "table" in element:
            for row in element["table"].get("tableRows", []):
                for cell in row.get("tableCells", []):
                    for cell_elem in cell.get("content", []):
                        if "paragraph" in cell_elem:
                            for pe in cell_elem["paragraph"].get("elements", []):
                                content = pe.get("textRun", {}).get("content", "")
                                if content:
                                    text_parts.append(content)
                    text_parts.append(" | ")
                text_parts.append("\n")

    return "".join(text_parts)


async def read_drive_file(
    access_token: str,
    file_id: str,
    max_chars: int = 8000,
) -> Dict[str, Any]:
    """
    Read the full text content of a Google Doc.

    Args:
        access_token: Valid Google OAuth access token.
        file_id: The Google Drive file ID of the document.
        max_chars: Maximum characters to return (default 8000 to stay within LLM limits).

    Returns:
        Dict with 'title', 'content' (plain text), and 'char_count'.
    """
    try:
        service = _docs_service(access_token)
        doc = service.documents().get(documentId=file_id).execute()

        title = doc.get("title", "Untitled")
        content = _extract_text_from_doc(doc)

        # Truncate if needed
        truncated = False
        if len(content) > max_chars:
            content = content[:max_chars]
            truncated = True

        logger.info("doc_read", file_id=file_id, title=title, chars=len(content))

        return {
            "success": True,
            "file_id": file_id,
            "title": title,
            "content": content,
            "char_count": len(content),
            "truncated": truncated,
        }
    except Exception as e:
        logger.error("doc_read_error", file_id=file_id, error=str(e))
        return {"success": False, "error": str(e), "content": ""}


# ── Tool Schema ────────────────────────────────────────────────

DOCS_TOOLS_SCHEMA = [
    {
        "name": "read_drive_file",
        "description": (
            "Read the full text content of a Google Doc. "
            "Use this to summarize, analyze, or answer questions about a document's content. "
            "Requires the file ID (e.g. '1abc123...'). If you only have a filename, you MUST call 'search_drive_files' first to obtain the ID."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "file_id": {
                    "type": "string",
                    "description": "The Google Drive file ID of the document to read.",
                },
                "max_chars": {
                    "type": "integer",
                    "description": "Maximum characters to read. Default 8000.",
                    "default": 8000,
                },
            },
            "required": ["file_id"],
        },
    },
]
