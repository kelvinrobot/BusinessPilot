"""The single entry point used by both the text chat endpoint and the voice pipeline,
so they share one memory + multi-agent code path (per the product spec)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import AgentContext, AgentResult
from app.agents.calendar_agent import CalendarAgent
from app.agents.document_agent import DocumentAgent
from app.agents.email_agent import EmailAgent
from app.agents.marketing_agent import MarketingAgent
from app.agents.memory_agent import MemoryAgent
from app.agents.planner_agent import PlannerAgent
from app.agents.research_agent import ResearchAgent
from app.agents.reviewer_agent import ReviewerAgent
from app.core.logging import get_logger
from app.db.models.agent_run import AgentRun
from app.repositories.agent_run_repository import AgentRunRepository
from app.repositories.user_repository import UserRepository

logger = get_logger(__name__)

_SPECIALISTS = [DocumentAgent(), ResearchAgent(), MarketingAgent(), EmailAgent(), CalendarAgent()]
AGENT_REGISTRY = {agent.name: agent for agent in _SPECIALISTS}
AGENT_DESCRIPTIONS = {agent.name: agent.description for agent in _SPECIALISTS}

_memory_agent = MemoryAgent()
_planner_agent = PlannerAgent(AGENT_DESCRIPTIONS)
_reviewer_agent = ReviewerAgent()


@dataclass
class OrchestratorResult:
    reply: str
    agent_results: list[AgentResult] = field(default_factory=list)
    pending_approvals: list[dict] = field(default_factory=list)
    documents: list[dict] = field(default_factory=list)
    agent_run_id: str | None = None


async def _run_step(context: AgentContext, agent_name: str, instruction: str) -> AgentResult:
    agent = AGENT_REGISTRY.get(agent_name)
    if agent is None:
        return AgentResult(agent=agent_name, success=False, summary="", error=f"Unknown agent '{agent_name}'")
    try:
        return await agent.run(context, instruction)
    except Exception as exc:
        logger.error("agent_step_failed", agent=agent_name, error=str(exc))
        return AgentResult(agent=agent_name, success=False, summary="", error=str(exc))


async def run_orchestrator(
    user_id: str,
    db: AsyncSession,
    conversation_id: str | None,
    user_message: str,
    history: list[dict[str, str]],
) -> OrchestratorResult:
    user = await UserRepository(db).get(user_id)
    user_timezone = user.timezone if user else "UTC"
    context = AgentContext(user_id=user_id, db=db, conversation_id=conversation_id, history=history, user_timezone=user_timezone)
    context.memory_context = await _memory_agent.retrieve_context(context, user_message)

    plan = await _planner_agent.plan(context, user_message)

    results: list[AgentResult] = []
    for step in plan.steps:
        results.append(await _run_step(context, step.agent, step.instruction))

    verdict = await _reviewer_agent.review(context, user_message, results, plan.direct_reply)

    if not verdict.approved and verdict.retry_step is not None and 0 <= verdict.retry_step < len(plan.steps):
        failing_step = plan.steps[verdict.retry_step]
        augmented_instruction = failing_step.instruction
        if verdict.retry_feedback:
            augmented_instruction += f"\n\nReviewer feedback to address: {verdict.retry_feedback}"
        results[verdict.retry_step] = await _run_step(context, failing_step.agent, augmented_instruction)
        verdict = await _reviewer_agent.review(context, user_message, results, plan.direct_reply)

    await _memory_agent.store_from_turn(context, user_message, verdict.final_reply)

    agent_run = AgentRun(
        user_id=user_id,
        conversation_id=conversation_id,
        goal=user_message,
        plan_json=json.dumps(
            {"steps": [{"agent": s.agent, "instruction": s.instruction} for s in plan.steps], "reasoning": plan.reasoning}
        ),
        status="completed" if verdict.approved else "completed_with_issues",
        result_json=json.dumps(
            [{"agent": r.agent, "success": r.success, "summary": r.summary, "data": r.data} for r in results]
        ),
    )
    await AgentRunRepository(db).add(agent_run)
    await db.commit()

    pending_approvals = []
    documents = []
    for r in results:
        if r.requires_approval:
            pending_approvals.append({"agent": r.agent, **r.data})
        if "document_id" in r.data:
            documents.append({"document_id": r.data["document_id"], "title": r.data.get("title"), "download_url": r.data.get("download_url")})

    return OrchestratorResult(
        reply=verdict.final_reply,
        agent_results=results,
        pending_approvals=pending_approvals,
        documents=documents,
        agent_run_id=agent_run.id,
    )
