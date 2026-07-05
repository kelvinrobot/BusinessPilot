from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from app.core.json_utils import extract_json
from app.core.logging import get_logger
from app.agents.base import AgentContext
from app.services.qwen.client import get_qwen_client

logger = get_logger(__name__)


@dataclass
class PlanStep:
    agent: str
    instruction: str


@dataclass
class Plan:
    steps: list[PlanStep] = field(default_factory=list)
    direct_reply: str | None = None
    reasoning: str = ""


def _build_system_prompt(agent_descriptions: dict[str, str]) -> str:
    roster = "\n".join(f"- {name}: {desc}" for name, desc in agent_descriptions.items())
    return f"""You are the Planner for BusinessPilot AI, a business executive assistant. \
Given the user's request, the business's remembered context, and recent conversation, \
decide how to fulfil it.

Available specialist agents you may delegate to:
{roster}

Rules:
- If the request is simple conversation, a question you can answer directly, or doesn't \
need a specialist (e.g. small talk, clarifying questions), set "steps" to [] and put your \
reply in "direct_reply".
- If the request needs one or more specialists (e.g. creating a document, drafting/reading \
email, scheduling, research, marketing content), list each as a step with the agent name \
and a clear, specific instruction for that agent. Order steps sensibly.
- Only delegate to agents that exist in the roster above.
- Keep "reasoning" brief (one sentence).

Respond ONLY with JSON of this exact shape:
{{"steps": [{{"agent": "<name>", "instruction": "<...>"}}], "direct_reply": "<string or null>", "reasoning": "<...>"}}"""


class PlannerAgent:
    name = "planner"

    def __init__(self, agent_descriptions: dict[str, str]):
        self.agent_descriptions = agent_descriptions

    async def plan(self, context: AgentContext, user_message: str) -> Plan:
        client = get_qwen_client()
        system_prompt = _build_system_prompt(self.agent_descriptions)
        user_prompt = f"""Remembered context about this business:
{context.memory_block()}

Recent conversation:
{context.history_block()}

User's new request:
{user_message}"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        try:
            result = await asyncio.to_thread(client.chat, messages, None, 0.2)
            parsed = extract_json(result.content)
        except Exception as exc:
            logger.error("planner_failed", error=str(exc))
            return Plan(direct_reply="I had trouble planning that request. Could you rephrase it?")

        steps = [
            PlanStep(agent=s["agent"], instruction=s["instruction"])
            for s in parsed.get("steps", [])
            if s.get("agent") in self.agent_descriptions
        ]
        return Plan(
            steps=steps,
            direct_reply=parsed.get("direct_reply"),
            reasoning=parsed.get("reasoning", ""),
        )
