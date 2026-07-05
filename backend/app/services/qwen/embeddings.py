from __future__ import annotations

import dashscope

from app.core.config import settings
from app.core.exceptions import IntegrationError
from app.core.logging import get_logger

logger = get_logger(__name__)


def embed_text(text: str) -> list[float]:
    """Embed a single string with Qwen's text-embedding-v3. Blocking call — callers in
    async code should wrap this with `asyncio.to_thread`."""
    try:
        response = dashscope.TextEmbedding.call(
            model=settings.qwen_embedding_model,
            input=text,
        )
    except Exception as exc:
        logger.error("qwen_embedding_failed", error=str(exc))
        raise IntegrationError(f"Qwen embedding request failed: {exc}") from exc

    if response.status_code != 200:
        logger.error("qwen_embedding_error", message=response.message)
        raise IntegrationError(f"Qwen embedding error: {response.message}")

    return response.output["embeddings"][0]["embedding"]


def embed_batch(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    try:
        response = dashscope.TextEmbedding.call(
            model=settings.qwen_embedding_model,
            input=texts,
        )
    except Exception as exc:
        logger.error("qwen_embedding_batch_failed", error=str(exc))
        raise IntegrationError(f"Qwen embedding request failed: {exc}") from exc

    if response.status_code != 200:
        raise IntegrationError(f"Qwen embedding error: {response.message}")

    items = sorted(response.output["embeddings"], key=lambda e: e["text_index"])
    return [item["embedding"] for item in items]
