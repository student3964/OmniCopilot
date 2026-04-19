"""
Google Drive Tool — list files, search, and fetch file metadata.
All functions are LangChain-compatible async tools.
"""

from typing import Any, Dict, List, Optional
import os
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials

from app.core.logging import get_logger

logger = get_logger(__name__)

# ── Helpers ───────────────────────────────────────────────────

def _drive_service(access_token: str):
    """Build a Drive API client from a raw access token."""
    creds = Credentials(token=access_token)
    return build("drive", "v3", credentials=creds, cache_discovery=False)


# ── Tool Functions ────────────────────────────────────────────

async def get_drive_files(
    access_token: str,
    max_results: int = 10,
    query: Optional[str] = None,
    file_type: Optional[str] = None,
    num_files: Optional[int] = None,  # Alias
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    List files from Google Drive.

    Args:
        access_token: Valid Google OAuth access token.
        max_results: Maximum number of files to return (default 10).
        query: Optional search query (Drive query syntax).
        file_type: Optional MIME type filter (e.g. 'application/vnd.google-apps.document').
        num_files: Alias for max_results.
    """
    # Handle aliases
    max_results = num_files or max_results
    try:
        service = _drive_service(access_token)

        q_parts = ["trashed = false"]
        if query:
            q_parts.append(f"name contains '{query}'")
        if file_type:
            q_parts.append(f"mimeType = '{file_type}'")

        full_query = " and ".join(q_parts)

        result = service.files().list(
            q=full_query,
            pageSize=max_results,
            fields="files(id, name, mimeType, modifiedTime, webViewLink, size, owners)",
            orderBy="modifiedTime desc",
        ).execute()

        files = result.get("files", [])
        logger.info("drive_files_fetched", count=len(files))

        return {
            "success": True,
            "count": len(files),
            "files": [
                {
                    "id": f["id"],
                    "name": f["name"],
                    "type": f.get("mimeType", "unknown"),
                    "modified": f.get("modifiedTime"),
                    "url": f.get("webViewLink"),
                    "owner": f.get("owners", [{}])[0].get("displayName", "Unknown"),
                }
                for f in files
            ],
        }
    except Exception as e:
        logger.error("drive_files_error", error=str(e))
        return {"success": False, "error": str(e), "files": []}


async def search_drive_files(
    access_token: str,
    search_term: str,
    max_results: int = 5,
    num_files: Optional[int] = None,  # Alias
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Search Google Drive files by name or content.

    Args:
        access_token: Valid Google OAuth access token.
        search_term: Text to search for in file names or full text.
        max_results: Maximum results to return.
    """
    return await get_drive_files(
        access_token=access_token,
        max_results=max_results,
        query=search_term,
    )


async def get_drive_file_metadata(
    access_token: str,
    file_id: str,
) -> Dict[str, Any]:
    """
    Get detailed metadata for a specific Drive file.

    Args:
        access_token: Valid Google OAuth access token.
        file_id: The Google Drive file ID.
    """
    try:
        service = _drive_service(access_token)
        file = service.files().get(
            fileId=file_id,
            fields="id, name, mimeType, modifiedTime, createdTime, webViewLink, size, owners, description",
        ).execute()

        return {"success": True, "file": file}
    except Exception as e:
        logger.error("drive_metadata_error", file_id=file_id, error=str(e))
        return {"success": False, "error": str(e)}


async def upload_to_drive(
    access_token: str,
    file_path: str,
    custom_name: Optional[str] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Upload a local file to Google Drive.
    ⚠️ SENSITIVE — requires user confirmation.

    Args:
        access_token: Valid Google OAuth access token.
        file_path: Absolute local path to the file to upload.
        custom_name: Optional new name for the file in Drive.
    """
    try:
        if not os.path.exists(file_path):
            return {"success": False, "error": f"File not found at path: {file_path}"}

        service = _drive_service(access_token)
        
        file_name = custom_name or os.path.basename(file_path)
        
        file_metadata = {'name': file_name}
        media = MediaFileUpload(
            file_path, 
            resumable=True
        )
        
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, name, webViewLink'
        ).execute()

        logger.info("drive_file_uploaded", file_id=file.get('id'), name=file_name)

        return {
            "success": True,
            "file_id": file.get('id'),
            "name": file.get('name'),
            "url": file.get('webViewLink')
        }
    except Exception as e:
        logger.error("drive_upload_error", error=str(e))
        return {"success": False, "error": str(e)}


# ── Tool Schema (for LLM function calling) ────────────────────

DRIVE_TOOLS_SCHEMA = [
    {
        "name": "get_drive_files",
        "description": "List or search files in the user's Google Drive. Use this when asked about documents, spreadsheets, presentations, or files stored in Drive.",
        "parameters": {
            "type": "object",
            "properties": {
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of files to return. Default is 10.",
                    "default": 10,
                },
                "query": {
                    "type": "string",
                    "description": "Search term to filter files by name.",
                },
                "file_type": {
                    "type": "string",
                    "description": "Filter by MIME type. E.g. 'application/vnd.google-apps.document' for Docs.",
                },
            },
            "required": [],
        },
    },
    {
        "name": "search_drive_files",
        "description": "Search for specific files in Google Drive by keywords.",
        "parameters": {
            "type": "object",
            "properties": {
                "search_term": {
                    "type": "string",
                    "description": "The keyword or phrase to search for in Drive.",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results.",
                    "default": 5,
                },
            },
            "required": ["search_term"],
        },
    },
    {
        "name": "upload_to_drive",
        "description": "⚠️ SENSITIVE: Upload an attached or local file to Google Drive. Always confirm with the user before executing.",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "The local path of the file to upload (usually obtained from file upload context).",
                },
                "custom_name": {
                    "type": "string",
                    "description": "Optional: A new name for the file in Google Drive.",
                },
            },
            "required": ["file_path"],
        },
        "requires_confirmation": True,
    },
]
