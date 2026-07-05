from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import AgentContext
from app.agents.document_agent import DocumentAgent
from app.api.deps import get_current_user, get_db
from app.core.exceptions import NotFoundError, ValidationAppError
from app.db.models.document import Document
from app.db.models.user import User
from app.repositories.document_repository import DocumentRepository
from app.schemas.document import DocumentGenerateRequest, DocumentRead
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/documents", tags=["documents"])
_document_agent = DocumentAgent()


@router.get("", response_model=list[DocumentRead])
async def list_documents(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[Document]:
    return await DocumentRepository(db).list_for_user(current_user.id, limit=limit)


@router.post("/generate", response_model=DocumentRead, status_code=201)
async def generate_document(
    payload: DocumentGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Document:
    context = AgentContext(user_id=current_user.id, db=db, conversation_id=None)
    result = await _document_agent.run(context, payload.instruction)
    if not result.success:
        raise ValidationAppError(result.summary or result.error or "Document generation failed.")

    document = await DocumentRepository(db).get(result.data["document_id"])

    await NotificationService(db).notify(
        current_user.id,
        type="document_ready",
        title=f"Document ready: {document.title}",
        body="Your document has finished generating and is ready to download.",
        link=f"/api/v1/documents/{document.id}/download",
    )
    return document


@router.get("/{document_id}/download")
async def download_document(
    document_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    document = await DocumentRepository(db).get(document_id)
    if document is None or document.user_id != current_user.id:
        raise NotFoundError("Document not found.")

    media_type = (
        "application/pdf"
        if document.file_format == "pdf"
        else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    filename = f"{document.title}.{document.file_format}"
    return FileResponse(document.file_path, media_type=media_type, filename=filename)
