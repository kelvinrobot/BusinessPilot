from __future__ import annotations

import asyncio
from dataclasses import dataclass

from app.agents.base import AgentContext, AgentResult
from app.core.json_utils import extract_json
from app.core.logging import get_logger
from app.services.qwen.client import get_qwen_client

logger = get_logger(__name__)

REVIEWER_SYSTEM_PROMPT = """You are the Reviewer for BusinessPilot AI. You receive the \
user's original goal and the results produced by specialist agents. Your job:

1. Judge whether the combined results actually satisfy the user's goal and are \
professional-quality.
2. Write the final reply to show the user: friendly, concise, professional executive- \
assistant tone. Mention any documents created, any drafts now pending the user's \
approval, and any failures plainly.
3. If something is clearly broken or missing (a step failed and nothing else covers it), \
set "verdict" to "needs_revision", say which step needs to be redone in "retry_step" \
(its index, 0-based), and give specific corrective feedback in "retry_feedback" to guide \
the redo. Otherwise set "verdict" to "approved", "retry_step" to null, "retry_feedback" \
to null.

Respond ONLY with JSON: {"verdict": "approved"|"needs_revision", "retry_step": <int|null>, \
"retry_feedback": "<string|null>", "final_reply": "<string>"}"""


@dataclass
class ReviewVerdict:
    approved: bool
    retry_step: int | None
    retry_feedback: str | None
    final_reply: str


class ReviewerAgent:
    name = "reviewer"

    async def review(
        self, context: AgentContext, goal: str, results: list[AgentResult], direct_reply: str | None
    ) -> ReviewVerdict:
        if direct_reply is not None and not results:
            return ReviewVerdict(approved=True, retry_step=None, retry_feedback=None, final_reply=direct_reply)

        client = get_qwen_client()
        results_text = "\n\n".join(
            f"[step {i}] agent={r.agent} success={r.success}\nsummary={r.summary}\nerror={r.error or '-'}"
            for i, r in enumerate(results)
        )
        messages = [
            {"role": "system", "content": REVIEWER_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"User's original goal:\n{goal}\n\nAgent results:\n{results_text}",
            },
        ]

        try:
            response = await asyncio.to_thread(client.chat, messages, None, 0.3)
            parsed = extract_json(response.content)
            return ReviewVerdict(
                approved=parsed.get("verdict") == "approved",
                retry_step=parsed.get("retry_step"),
                retry_feedback=parsed.get("retry_feedback"),
                final_reply=parsed.get("final_reply", "Here are the results of your request."),
            )
        except Exception as exc:
            logger.error("reviewer_failed", error=str(exc))
            fallback = "\n\n".join(r.summary for r in results if r.success) or "Something went wrong processing your request."
            return ReviewVerdict(approved=True, retry_step=None, retry_feedback=None, final_reply=fallback)
