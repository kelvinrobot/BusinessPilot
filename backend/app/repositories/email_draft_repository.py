from app.db.models.email_draft import EmailDraft
from app.repositories.base_repository import BaseRepository


class EmailDraftRepository(BaseRepository[EmailDraft]):
    model = EmailDraft
