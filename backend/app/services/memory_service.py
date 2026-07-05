"""Persistent semantic memory: stores durable facts/preferences about a user's
business with an embedding, retrieves the most relevant ones as context for future
agent runs, and decays/forgets stale items so memory stays useful rather than just
growing forever."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.base import utcnow
from app.db.models.memory import MemoryItem
from app.repositories.memory_repository import MemoryRepository
from app.services.qwen.client import get_qwen_client
from app.services.qwen.embeddings import embed_text

logger = get_logger(__name__)

DEDUPE_SIMILARITY_THRESHOLD = 0.92
MIN_IMPORTANCE_BEFORE_FORGET = 0.05
DECAY_HALF_LIFE_DAYS = 45.0

FACT_EXTRACTION_SYSTEM_PROMPT = """You extract durable facts worth remembering long-term \
about a business owner from a conversation excerpt. Only extract things that will still \
be true/useful weeks from now: business profile details, client/project names, stated \
preferences (writing style, meeting times, tone), goals, and decisions. Do NOT extract \
small talk or one-off requests.

Respond ONLY with a JSON array, each item: {"content": str, "category": \
"profile"|"preference"|"project"|"fact", "importance": float between 0 and 1}. \
If nothing is worth remembering, respond with []."""


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    va, vb = np.array(a), np.array(b)
    denom = np.linalg.norm(va) * np.linalg.norm(vb)
    if denom == 0:
        return 0.0
    return float(np.dot(va, vb) / denom)


def _recency_factor(last_accessed_at: datetime) -> float:
    now = datetime.now(timezone.utc)
    # SQLite returns naive datetimes even for timezone=True columns; treat as UTC.
    if last_accessed_at.tzinfo is None:
        last_accessed_at = last_accessed_at.replace(tzinfo=timezone.utc)
    age_days = max((now - last_accessed_at).total_seconds() / 86400, 0.0)
    return 0.5 ** (age_days / DECAY_HALF_LIFE_DAYS)


class MemoryService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = MemoryRepository(session)

    async def store(self, user_id: str, content: str, category: str = "fact", importance: float = 0.5) -> MemoryItem:
        embedding = await asyncio.to_thread(embed_text, content)

        existing_items = await self.repo.all_for_user(user_id)
        for item in existing_items:
            existing_embedding = json.loads(item.embedding_json)
            if _cosine_similarity(embedding, existing_embedding) >= DEDUPE_SIMILARITY_THRESHOLD:
                item.content = content
                item.importance = max(item.importance, importance)
                item.last_accessed_at = utcnow()
                await self.session.flush()
                return item

        new_item = MemoryItem(
            user_id=user_id,
            content=content,
            embedding_json=json.dumps(embedding),
            category=category,
            importance=importance,
        )
        await self.repo.add(new_item)
        return new_item

    async def retrieve(self, user_id: str, query: str, top_k: int = 6) -> list[MemoryItem]:
        items = await self.repo.all_for_user(user_id)
        if not items:
            return []

        query_embedding = await asyncio.to_thread(embed_text, query)

        scored: list[tuple[float, MemoryItem]] = []
        for item in items:
            similarity = _cosine_similarity(query_embedding, json.loads(item.embedding_json))
            score = similarity * item.importance * _recency_factor(item.last_accessed_at)
            scored.append((score, item))

        scored.sort(key=lambda pair: pair[0], reverse=True)
        top_items = [item for _, item in scored[:top_k]]

        for item in top_items:
            item.last_accessed_at = utcnow()
        await self.session.flush()

        return top_items

    async def extract_and_store_facts(self, user_id: str, conversation_excerpt: str) -> list[MemoryItem]:
        client = get_qwen_client()
        messages = [
            {"role": "system", "content": FACT_EXTRACTION_SYSTEM_PROMPT},
            {"role": "user", "content": conversation_excerpt},
        ]

        try:
            result = await asyncio.to_thread(client.chat, messages, None, 0.1)
            facts = json.loads(result.content)
        except Exception as exc:
            logger.warning("memory_fact_extraction_failed", error=str(exc))
            return []

        stored: list[MemoryItem] = []
        for fact in facts if isinstance(facts, list) else []:
            content = fact.get("content")
            if not content:
                continue
            item = await self.store(
                user_id,
                content=content,
                category=fact.get("category", "fact"),
                importance=float(fact.get("importance", 0.5)),
            )
            stored.append(item)

        return stored

    async def decay_and_forget(self, user_id: str) -> int:
        """Periodic housekeeping: shrink importance of stale items and delete anything
        that has decayed below the keep threshold. Returns the number forgotten."""
        items = await self.repo.all_for_user(user_id)
        forgotten = 0
        for item in items:
            item.importance *= _recency_factor(item.last_accessed_at)
            if item.importance < MIN_IMPORTANCE_BEFORE_FORGET:
                await self.repo.delete(item)
                forgotten += 1
        await self.session.flush()
        return forgotten
