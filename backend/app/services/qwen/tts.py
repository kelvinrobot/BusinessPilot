"""
TTS is handled by the browser's SpeechSynthesis API.
This module is intentionally empty — the OpenAI-compatible /audio/speech endpoint
is not available on this DashScope workspace (returns 404), and the native
cosyvoice-v2 model returns ModelNotFound for this account.

The voice WebSocket sends text replies; the browser converts them to speech locally.
"""
