"""
Google Drive File Reader — Overhauled to be Universal.
Supports Google Docs, PDFs, and plain text files using the Drive API.
This version bypasses the need for the Google Docs API by using the Drive Export feature.
"""

from typing import Any, Dict, Optional
import io
from pypdf import PdfReader
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2.credentials import Credentials

from app.core.logging import get_logger

logger = get_logger(__name__)


def _drive_service(access_token: str):
    """Build a Drive API (v3) client."""
    creds = Credentials(token=access_token)
    return build("drive", "v3", credentials=creds, cache_discovery=False)


async def read_drive_file(
    access_token: str,
    file_id: str,
    max_chars: int = 8000,
) -> Dict[str, Any]:
    """
    Universally read the content of a Google Drive file (Docs, PDFs, Text).
    
    Args:
        access_token: Valid Google OAuth access token.
        file_id: The ID of the file to read.
        max_chars: Maximum characters to return.
    """
    try:
        service = _drive_service(access_token)
        
        # 1. Fetch file metadata to determine MIME type
        file_meta = service.files().get(
            fileId=file_id, 
            fields="id, name, mimeType, description, size, createdTime, modifiedTime, owners, webViewLink",
            supportsAllDrives=True,
        ).execute()
        
        mime_type = file_meta.get("mimeType", "")
        file_name = file_meta.get("name", "Untitled")
        
        content = ""
        
        # 2. Extract content based on type
        # Case A: Google Doc -> Export to plain text
        if mime_type == "application/vnd.google-apps.document":
            request = service.files().export_media(
                fileId=file_id, 
                mimeType="text/plain"
            )
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
            fh.seek(0)
            content = fh.getvalue().decode("utf-8", errors="replace")

        # Case B: Google Sheets -> Export to CSV
        elif mime_type == "application/vnd.google-apps.spreadsheet":
            request = service.files().export_media(
                fileId=file_id, 
                mimeType="text/csv"
            )
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
            fh.seek(0)
            content = fh.getvalue().decode("utf-8", errors="replace")

        # Case C: PDF -> Extract text using pypdf
        elif mime_type == "application/pdf":
            request = service.files().get_media(
                fileId=file_id,
                supportsAllDrives=True,
            )
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
            
            fh.seek(0)
            # Use pypdf to extract text
            reader = PdfReader(fh)
            text_parts = []
            for page in reader.pages:
                text_parts.append(page.extract_text() or "")
            content = "\n".join(text_parts).strip()
            
            if not content:
                # Scanned PDF - use filename and metadata to infer what it is
                name_lower = file_name.lower()
                doc_type = "document"
                if any(w in name_lower for w in ["certificate", "cert", "completion", "award"]):
                    doc_type = "certificate or credential"
                elif any(w in name_lower for w in ["invoice", "bill", "receipt"]):
                    doc_type = "financial document (invoice/receipt)"
                elif any(w in name_lower for w in ["report", "summary", "analysis"]):
                    doc_type = "report or summary document"
                elif any(w in name_lower for w in ["letter", "memo", "notice"]):
                    doc_type = "letter or official notice"
                elif any(w in name_lower for w in ["igot", "karmayogi", "government", "ministry"]):
                    doc_type = "government training or official document"
                
                owner_info = ""
                owners = file_meta.get("owners", [])
                if owners:
                    owner_info = f" Owner: {owners[0].get('displayName', 'Unknown')}."
                
                content = (
                    f"[SCANNED PDF - No extractable text]\n"
                    f"Based on the filename '{file_name}', this appears to be a **{doc_type}**.\n"
                    f"Created: {file_meta.get('createdTime', 'Unknown')}. "
                    f"Last modified: {file_meta.get('modifiedTime', 'Unknown')}.{owner_info}\n"
                    f"To read the actual content, OCR (optical character recognition) would be required."
                )

        # Case D: Plain text or Code files
        elif "text/" in mime_type or mime_type in ["application/json", "application/javascript"]:
            request = service.files().get_media(
                fileId=file_id,
                supportsAllDrives=True,
            )
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
            fh.seek(0)
            content = fh.getvalue().decode("utf-8", errors="replace")

        else:
            return {
                "success": False, 
                "error": f"Unsupported file type: {mime_type}. Currently support: Docs, Sheets, PDFs, and Text files."
            }

        # 3. Handle truncation and result
        truncated = False
        if len(content) > max_chars:
            content = content[:max_chars]
            truncated = True

        logger.info("universal_read_success", file_id=file_id, type=mime_type, chars=len(content))

        return {
            "success": True,
            "file_id": file_id,
            "title": file_name,
            "content": content,
            "char_count": len(content),
            "truncated": truncated,
            "type": mime_type
        }

    except Exception as e:
        logger.error("universal_read_error", file_id=file_id, error=str(e))
        return {"success": False, "error": str(e), "content": ""}


# ── Tool Schema ────────────────────────────────────────────────

DOCS_TOOLS_SCHEMA = [
    {
        "name": "read_drive_file",
        "description": (
            "Read the content of ANY common Drive file (Google Docs, PDFs, Text files). "
            "Use this to summarize, analyze, or answer questions about a file's content. "
            "Requires the file ID. If you only have a filename, search for it first."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "file_id": {
                    "type": "string",
                    "description": "The Google Drive file ID to read.",
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
