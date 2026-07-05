from __future__ import annotations

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.services.memory_service import MemoryService


class MemoryAgent(BaseAgent):
    """Retrieves relevant long-term memory before a run and updates it afterwards.
    Called directly by the Orchestrator (not dispatched as a planned step) since every
    run needs memory context, but exposed as its own agent for the spec's multi-agent
    model and so it can be unit tested in isolation."""

    name = "memory"
    description = "Retrieves and updates long-term business memory (not directly delegatable)."

    async def run(self, context: AgentContext, instruction: str) -> AgentResult:
        service = MemoryService(context.db)
        items = await service.retrieve(context.user_id, instruction)
        return AgentResult(
            agent=self.name,
            success=True,
            summary=f"Retrieved {len(items)} relevant memory items.",
            data={"items": [i.content for i in items]},
        )

    async def retrieve_context(self, context: AgentContext, query: str) -> list[str]:
        service = MemoryService(context.db)
        items = await service.retrieve(context.user_id, query)
        return [item.content for item in items]

    async def store_from_turn(self, context: AgentContext, user_message: str, assistant_reply: str) -> None:
        service = MemoryService(context.db)
        excerpt = f"User: {user_message}\nAssistant: {assistant_reply}"
        await service.extract_and_store_facts(context.user_id, excerpt)
