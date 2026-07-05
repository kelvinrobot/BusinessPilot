from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, new_uuid, utcnow


class MemoryItem(TimestampMixin, Base):
    """A durable fact/preference about the user's business, stored with an embedding
    so it can be semantically retrieved as context for future agent runs."""

    __tablename__ = "memory_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # JSON-encoded list[float]. Portable now; migrate to a native vector column + ANN
    # index (pgvector) when moving off SQLite.
    embedding_json: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(32), default="fact")  # profile|preference|project|fact
    importance: Mapped[float] = mapped_column(Float, default=0.5)
    last_accessed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
