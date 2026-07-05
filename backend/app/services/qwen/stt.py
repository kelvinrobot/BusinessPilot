"""
STT is handled by the browser's Web Speech API.
This module is intentionally empty — no server-side ASR models are accessible
on this DashScope workspace (paraformer-realtime-v2 and qwen3-asr-flash-realtime
both return ModelNotFound for this account).

The voice WebSocket (/api/v1/voice/ws) now receives text transcripts as JSON
from the browser rather than raw PCM audio frames.
"""
