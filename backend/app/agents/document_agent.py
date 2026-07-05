from __future__ import annotations

import asyncio

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.core.json_utils import extract_json
from app.core.logging import get_logger
from app.services.document_service import DocumentSection, DocumentService
from app.services.qwen.client import get_qwen_client

logger = get_logger(__name__)

DOCUMENT_SYSTEM_PROMPT = """You are the Document Agent for BusinessPilot AI. You write \
complete, professional, ready-to-send business documents: business plans, pitch decks, \
executive summaries, financial projection narratives, project proposals, SWOT analyses, \
competitor analyses, product requirement documents, technical docs, meeting agendas/ \
minutes, and similar. Write real, specific, well-organized content using the business \
context provided -- never a placeholder or outline-only skeleton.

Respond ONLY with JSON of this shape:
{"title": "<document title>", "doc_type": "<short slug e.g. business_plan>", \
"format": "docx"|"pdf", "sections": [{"heading": "<section heading>", "body": "<full \
section content, multiple paragraphs allowed>"}]}

Choose "pdf" for short/visual documents (one-pagers, agendas) and "docx" for documents \
the user will likely want to keep editing (plans, proposals, reports). Include at least \
3 sections for any substantial document."""


class DocumentAgent(BaseAgent):
    name = "document"
    description = (
        "Creates real downloadable business documents (.docx/.pdf): business plans, "
        "pitch decks, proposals, SWOT/competitor analyses, reports, agendas, and more."
    )

    async def run(self, context: AgentContext, instruction: str) -> AgentResult:
        client = get_qwen_client()
        messages = [
            {"role": "system", "content": DOCUMENT_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Business context:\n{context.memory_block()}\n\n"
                    f"Document request:\n{instruction}"
                ),
            },
        ]

        try:
            response = await asyncio.to_thread(client.chat, messages, None, 0.5)
            parsed = extract_json(response.content)
            sections = [
                DocumentSection(heading=s["heading"], body=s["body"])
                for s in parsed["sections"]
            ]
        except Exception as exc:
            logger.error("document_agent_generation_failed", error=str(exc))
            return AgentResult(
                agent=self.name,
                success=False,
                summary="Failed to draft the document content.",
                error=str(exc),
            )

        try:
            service = DocumentService(context.db)
            document = await service.create_document(
                user_id=context.user_id,
                title=parsed["title"],
                doc_type=parsed.get("doc_type", "document"),
                file_format=parsed.get("format", "docx"),
                sections=sections,
            )
        except Exception as exc:
            logger.error("document_agent_render_failed", error=str(exc))
            return AgentResult(
                agent=self.name,
                success=False,
                summary="Drafted the content but failed to render the file.",
                error=str(exc),
            )

        return AgentResult(
            agent=self.name,
            success=True,
            summary=f'Created "{document.title}" ({document.file_format}) with {len(sections)} sections.',
            data={
                "document_id": document.id,
                "title": document.title,
                "file_format": document.file_format,
                "download_url": f"/api/v1/documents/{document.id}/download",
            },
        )
