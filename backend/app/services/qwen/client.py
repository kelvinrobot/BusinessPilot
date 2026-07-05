"""Thin wrapper around the DashScope SDK for Qwen Cloud chat/tool-calling.

All agent reasoning in BusinessPilot goes through this module so there is exactly one
place that knows how to talk to Qwen, handles retries/errors, and shapes
request/response payloads consistently for the rest of the app.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import dashscope
from dashscope.api_entities.dashscope_response import GenerationResponse

from app.core.config import settings
from app.core.exceptions import IntegrationError
from app.core.logging import get_logger

logger = get_logger(__name__)

dashscope.api_key = settings.qwen_api_key
dashscope.base_http_api_url = settings.dashscope_base_url
# Derive WebSocket endpoint from HTTP base URL so STT/TTS use the same region.
# e.g. https://dashscope-intl.aliyuncs.com/api/v1 → wss://dashscope-intl.aliyuncs.com/api-ws/v1/inference
dashscope.base_websocket_api_url = (
    settings.dashscope_base_url.replace("https://", "wss://").replace("/api/v1", "/api-ws/v1/inference")
)


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class ChatResult:
    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    raw_message: dict[str, Any] = field(default_factory=dict)
    finish_reason: str = "stop"


class QwenClient:
    """Synchronous-under-the-hood DashScope calls, exposed as async for FastAPI.

    The DashScope Python SDK is itself synchronous/blocking, so calls are run in a
    worker thread via `asyncio.to_thread` at the call sites in agents/services.
    """

    def __init__(self, model: str | None = None):
        self.model = model or settings.qwen_chat_model

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.4,
        tool_choice: str | dict[str, Any] = "auto",
    ) -> ChatResult:
        try:
            response: GenerationResponse = dashscope.Generation.call(
                model=self.model,
                messages=messages,
                tools=tools,
                tool_choice=tool_choice if tools else None,
                result_format="message",
                temperature=temperature,
            )
        except Exception as exc:  # network/SDK-level failure
            logger.error("qwen_chat_failed", error=str(exc), model=self.model)
            raise IntegrationError(f"Qwen chat request failed: {exc}") from exc

        if response.status_code != 200:
            logger.error(
                "qwen_chat_error",
                status_code=response.status_code,
                message=response.message,
                request_id=getattr(response, "request_id", None),
            )
            raise IntegrationError(f"Qwen chat error: {response.message}")

        choice = response.output.choices[0]
        message = choice["message"]

        tool_calls: list[ToolCall] = []
        for tc in message.get("tool_calls", []) or []:
            function = tc.get("function", {})
            try:
                arguments = json.loads(function.get("arguments") or "{}")
            except json.JSONDecodeError:
                arguments = {}
            tool_calls.append(
                ToolCall(id=tc.get("id", ""), name=function.get("name", ""), arguments=arguments)
            )

        return ChatResult(
            content=message.get("content") or "",
            tool_calls=tool_calls,
            raw_message=message,
            finish_reason=choice.get("finish_reason", "stop"),
        )


def get_qwen_client(model: str | None = None) -> QwenClient:
    return QwenClient(model=model)
