import os
import uuid
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from typing import Dict, Any, Optional
import io
from pypdf import PdfReader
from app.routes.auth import get_current_user
from app.models.db import User, get_db
from app.services.chat_service import save_message
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/chat", tags=["upload"])

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/upload")
async def upload_file(
    conversation_id: Optional[str] = None,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Handle file upload, extract text content, and store locally.
    If conversation_id is provided, persists context to the chat history.
    """
    filename = file.filename
    if not filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    file_bytes = await file.read()
    content = ""
    file_type = ""

    # 1. Save locally for tools to access
    unique_filename = f"{uuid.uuid4()}_{filename}"
    local_path = os.path.abspath(os.path.join(UPLOAD_DIR, unique_filename))
    
    with open(local_path, "wb") as f:
        f.write(file_bytes)

    try:
        # 2. Extract text for context
        if filename.lower().endswith(".pdf"):
            file_type = "pdf"
            reader = PdfReader(io.BytesIO(file_bytes))
            text_parts = []
            for page in reader.pages:
                text_parts.append(page.extract_text() or "")
            content = "\n".join(text_parts)
        
        elif filename.lower().endswith((".txt", ".md", ".py", ".js", ".ts")):
            file_type = "text"
            content = file_bytes.decode("utf-8")
        
        else:
            # We still save it, but we can't extract text
            file_type = "binary"
            content = f"[Binary file: {filename}]"

        # 3. Persist to DB if conversation context exists
        if conversation_id:
            try:
                conv_uuid = uuid.UUID(conversation_id)
                await save_message(
                    db=db,
                    conversation_id=conv_uuid,
                    role="system",
                    content=f"Uploaded file: {filename}\nLocal Path: {local_path}\n\n[FILE CONTENT]:\n{content[:10000]}"
                )
                logger.info("upload_persisted_to_db", conversation_id=conversation_id, filename=filename)
            except Exception as e:
                logger.error("upload_persistence_error", error=str(e))

        return {
            "filename": filename,
            "content": content,
            "type": file_type,
            "char_count": len(content),
            "local_path": local_path
        }

    except Exception as e:
        # Clean up if processing fails? Actually, better keep it if the user wants to upload anyway
        raise HTTPException(status_code=500, detail=f"File processing error: {str(e)}")
