from __future__ import annotations

import asyncio

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.core.json_utils import extract_json
from app.core.logging import get_logger
from app.services.document_service import DocumentSection, DocumentService
from app.services.qwen.client import get_qwen_client

logger = get_logger(__name__)

_RESPONSE_SHAPE = """Respond ONLY with JSON of this shape:
{"reply": "<conversational summary of what you produced, shown directly to the user>", \
"export_as_document": <true|false>, "title": "<title if exporting>", \
"sections": [{"heading": "...", "body": "..."}] (only if exporting, else [])}

Set "export_as_document" to true only if the user is asking for something they would \
want as a saved file (a report, plan, campaign deck, analysis document). For a quick \
question or short answer, set it to false and put your full answer in "reply"."""


class ContentAgentBase(BaseAgent):
    """Shared behavior for agents that generate content via Qwen and optionally export
    the result as a real downloadable document (Research, Marketing)."""

    system_prompt: str = ""

    async def run(self, context: AgentContext, instruction: str) -> AgentResult:
        client = get_qwen_client()
        messages = [
            {"role": "system", "content": f"{self.system_prompt}\n\n{_RESPONSE_SHAPE}"},
            {
                "role": "user",
                "content": f"Business context:\n{context.memory_block()}\n\nRequest:\n{instruction}",
            },
        ]

        try:
            response = await asyncio.to_thread(client.chat, messages, None, 0.5)
            parsed = extract_json(response.content)
        except Exception as exc:
            logger.error(f"{self.name}_generation_failed", error=str(exc))
            return AgentResult(
                agent=self.name, success=False, summary="Failed to generate content.", error=str(exc)
            )

        if not parsed.get("export_as_document"):
            return AgentResult(agent=self.name, success=True, summary=parsed.get("reply", ""))

        try:
            sections = [DocumentSection(heading=s["heading"], body=s["body"]) for s in parsed["sections"]]
            document = await DocumentService(context.db).create_document(
                user_id=context.user_id,
                title=parsed.get("title", f"{self.name.title()} output"),
                doc_type=self.name,
                file_format="docx",
                sections=sections,
            )
        except Exception as exc:
            logger.error(f"{self.name}_export_failed", error=str(exc))
            return AgentResult(
                agent=self.name,
                success=True,
                summary=parsed.get("reply", "") + "\n\n(Could not save this as a file.)",
            )

        return AgentResult(
            agent=self.name,
            success=True,
            summary=parsed.get("reply", "") + f'\n\nSaved as "{document.title}".',
            data={
                "document_id": document.id,
                "title": document.title,
                "download_url": f"/api/v1/documents/{document.id}/download",
            },
        )
