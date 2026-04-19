"""
Notion Tool — read pages, databases, search content, and create pages.
Create/update operations are SENSITIVE and require user confirmation.
"""

from typing import Any, Dict, List, Optional
from notion_client import AsyncClient

from app.core.logging import get_logger

logger = get_logger(__name__)


def _notion_client(access_token: str) -> AsyncClient:
    return AsyncClient(auth=access_token)


def _extract_rich_text(rich_text_array: list) -> str:
    """Extract plain text from Notion rich_text array."""
    return "".join([t.get("plain_text", "") for t in rich_text_array])


def _extract_page_content(blocks: list, max_blocks: int = 50) -> str:
    """Recursively extract text from Notion block content."""
    lines = []
    for block in blocks[:max_blocks]:
        block_type = block.get("type", "")
        block_data = block.get(block_type, {})

        rich_text = block_data.get("rich_text", [])
        text = _extract_rich_text(rich_text)

        if block_type == "heading_1":
            lines.append(f"# {text}")
        elif block_type == "heading_2":
            lines.append(f"## {text}")
        elif block_type == "heading_3":
            lines.append(f"### {text}")
        elif block_type in ("paragraph", "quote"):
            lines.append(text)
        elif block_type == "bulleted_list_item":
            lines.append(f"• {text}")
        elif block_type == "numbered_list_item":
            lines.append(f"1. {text}")
        elif block_type == "to_do":
            checked = "✅" if block_data.get("checked") else "☐"
            lines.append(f"{checked} {text}")
        elif block_type == "code":
            lang = block_data.get("language", "")
            lines.append(f"```{lang}\n{text}\n```")
        elif block_type == "divider":
            lines.append("---")
        elif block_type == "callout":
            icon = block_data.get("icon", {}).get("emoji", "💡")
            lines.append(f"{icon} {text}")

        # Add newline after each block
        if text or block_type in ("divider", "heading_1", "heading_2", "heading_3"):
            lines.append("")

    return "\n".join(lines)


def _format_page(page: dict) -> dict:
    """Format a Notion page object into clean dict."""
    props = page.get("properties", {})

    # Try to extract title from Name or Title property
    title = ""
    for key in ("Name", "Title", "title"):
        prop = props.get(key, {})
        rt = prop.get("title", prop.get("rich_text", []))
        if rt:
            title = _extract_rich_text(rt)
            break

    return {
        "id": page["id"],
        "title": title or "(Untitled)",
        "url": page.get("url", ""),
        "created_time": page.get("created_time", ""),
        "last_edited_time": page.get("last_edited_time", ""),
    }


async def search_notion(
    access_token: str,
    query: str,
    filter_type: Optional[str] = None,
    page_size: int = 10,
    num_pages: Optional[int] = None,  # Alias
    count: Optional[int] = None,      # Alias
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Search across all Notion pages and databases.

    Args:
        access_token: Notion OAuth access token.
        query: Search query string.
        filter_type: 'page' or 'database' (optional filter).
        page_size: Number of results.
        num_pages: Alias for page_size.
        count: Alias for page_size.
    """
    # Handle aliases
    page_size = num_pages or count or page_size
    try:
        client = _notion_client(access_token)

        params: dict = {"query": query, "page_size": page_size}
        if filter_type:
            params["filter"] = {"value": filter_type, "property": "object"}

        response = await client.search(**params)
        results = response.get("results", [])

        pages = [_format_page(p) for p in results if p.get("object") in ("page", "database")]
        logger.info("notion_search", query=query, count=len(pages))

        msg = ""
        if not pages:
            msg = "No results found. Note: Notion integrations can only see pages explicitly shared with them (click '...' -> 'Add connections' in Notion)."

        return {"success": True, "query": query, "results": pages, "note": msg}

    except Exception as e:
        logger.error("notion_search_error", query=query, error=str(e))
        return {"success": False, "error": str(e), "results": []}


async def get_notion_page(
    access_token: str,
    page_id: str,
) -> Dict[str, Any]:
    """
    Retrieve a Notion page with its full content.

    Args:
        access_token: Notion OAuth access token.
        page_id: The Notion page ID (UUID format).
    """
    try:
        client = _notion_client(access_token)

        # Get page metadata
        page = await client.pages.retrieve(page_id=page_id)
        formatted = _format_page(page)

        # Get page blocks (content)
        blocks_response = await client.blocks.children.list(block_id=page_id, page_size=100)
        blocks = blocks_response.get("results", [])
        content = _extract_page_content(blocks)

        logger.info("notion_page_read", page_id=page_id, title=formatted["title"])

        return {
            "success": True,
            "page": formatted,
            "content": content,
            "block_count": len(blocks),
        }

    except Exception as e:
        logger.error("notion_page_error", page_id=page_id, error=str(e))
        return {"success": False, "error": str(e)}


async def list_notion_databases(
    access_token: str,
) -> Dict[str, Any]:
    """List all Notion databases the integration can access."""
    try:
        client = _notion_client(access_token)
        response = await client.search(filter={"value": "database", "property": "object"}, page_size=20)
        databases = response.get("results", [])

        return {
            "success": True,
            "databases": [
                {
                    "id": db["id"],
                    "title": _extract_rich_text(db.get("title", [])) or "(Untitled DB)",
                    "url": db.get("url", ""),
                }
                for db in databases
            ],
        }
    except Exception as e:
        logger.error("notion_databases_error", error=str(e))
        return {"success": False, "error": str(e), "databases": []}


async def create_notion_page(
    access_token: str,
    parent_page_id: str,
    title: str,
    content: str,
) -> Dict[str, Any]:
    """
    Create a new Notion page under a parent page.
    ⚠️ SENSITIVE — requires user confirmation before execution.

    Args:
        access_token: Notion OAuth access token.
        parent_page_id: ID of the parent page.
        title: New page title.
        content: Page content as plain text (will be created as a paragraph).
    """
    try:
        client = _notion_client(access_token)

        new_page = await client.pages.create(
            parent={"page_id": parent_page_id},
            properties={
                "title": {"title": [{"type": "text", "text": {"content": title}}]}
            },
            children=[
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"type": "text", "text": {"content": content[:2000]}}]
                    },
                }
            ],
        )

        logger.info("notion_page_created", page_id=new_page["id"], title=title)
        return {
            "success": True,
            "page_id": new_page["id"],
            "url": new_page.get("url", ""),
            "title": title,
        }
    except Exception as e:
        logger.error("notion_create_page_error", error=str(e))
        return {"success": False, "error": str(e)}


# ── Tool Schema ────────────────────────────────────────────────

NOTION_TOOLS_SCHEMA = [
    {
        "name": "search_notion",
        "description": "Search across all Notion pages and databases. Use this to find notes, documents, projects in Notion.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query string."},
                "filter_type": {"type": "string", "description": "Filter to 'page' or 'database' (optional)."},
                "page_size": {"type": "integer", "description": "Number of results. Default 10.", "default": 10},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_notion_page",
        "description": "Read the full content of a Notion page. Requires the page ID from search_notion.",
        "parameters": {
            "type": "object",
            "properties": {
                "page_id": {"type": "string", "description": "The Notion page UUID."},
            },
            "required": ["page_id"],
        },
    },
    {
        "name": "list_notion_databases",
        "description": "List all Notion databases accessible to the integration.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "create_notion_page",
        "description": "⚠️ SENSITIVE: Create a new Notion page. Always confirm with user before creating.",
        "parameters": {
            "type": "object",
            "properties": {
                "parent_page_id": {"type": "string", "description": "ID of the parent page."},
                "title": {"type": "string", "description": "Title of the new page."},
                "content": {"type": "string", "description": "Content for the page body."},
            },
            "required": ["parent_page_id", "title", "content"],
        },
        "requires_confirmation": True,
    },
]
