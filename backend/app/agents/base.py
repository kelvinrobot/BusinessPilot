from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class AgentContext:
    """Shared state passed to every agent in one orchestrator run."""

    user_id: str
    db: AsyncSession
    conversation_id: str | None
    user_timezone: str = "UTC"
    memory_context: list[str] = field(default_factory=list)
    history: list[dict[str, str]] = field(default_factory=list)
    shared_state: dict[str, Any] = field(default_factory=dict)

    def memory_block(self) -> str:
        if not self.memory_context:
            return "(no prior memory on file for this user yet)"
        return "\n".join(f"- {m}" for m in self.memory_context)

    def history_block(self, limit: int = 8) -> str:
        if not self.history:
            return "(no prior messages in this conversation)"
        recent = self.history[-limit:]
        return "\n".join(f"{m['role']}: {m['content']}" for m in recent)


@dataclass
class AgentResult:
    agent: str
    success: bool
    summary: str
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    requires_approval: bool = False


class BaseAgent(ABC):
    name: str = "base"
    description: str = "Base agent"

    @abstractmethod
    async def run(self, context: AgentContext, instruction: str) -> AgentResult:
        raise NotImplementedError
