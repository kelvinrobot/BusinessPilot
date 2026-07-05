# Qwen Cloud Environment Discovery Report

Workspace: `dashscope-intl.aliyuncs.com` (international)
API key prefix: `sk-ws-H.LIYHEX...`
Discovery date: 2026-06-30

---

## Available Models

### Chat / LLM
| Model | API | Status |
|---|---|---|
| `qwen-plus` | OpenAI-compat + Native DashScope | **Available** |
| `qwen-turbo` | OpenAI-compat + Native DashScope | **Available** |
| `qwen-max` | OpenAI-compat + Native DashScope | **Available** |
| `qwen3-max` | Native DashScope | **Available** |
| `qwen3-omni-flash` | OpenAI-compat (text only) | **Available** |
| `qwen3.5-omni-flash` | OpenAI-compat (text only) | **Available** |
| `qwen-omni-turbo` | OpenAI-compat (text only) | **Available** |
| `qwq-plus` | OpenAI-compat | Available (in model list) |

> **Used by BusinessPilot:** `qwen-plus` via Native DashScope SDK
> (`dashscope.Generation` with tool-calling, not the OpenAI-compat endpoint,
> since the codebase uses structured tool-calling which the compat endpoint also
> supports but the native SDK was already in place and working).

### Embedding
| Model | API | Status | Dimension |
|---|---|---|---|
| `text-embedding-v3` | Native DashScope REST | **Available** | 1024 |
| `text-embedding-v4` | OpenAI-compat + Native | **Available** | 1024 |

> **Used by BusinessPilot:** `text-embedding-v3` via Native DashScope SDK.

### Vision / Multimodal
| Model | API | Status |
|---|---|---|
| `qwen-vl-plus` | Native DashScope | **Available** |
| `qwen-vl-max` | Native DashScope | **Available** |

### Speech Recognition (ASR)
| Model | API | Status |
|---|---|---|
| `paraformer-realtime-v2` | Native DashScope WebSocket SDK | **ModelNotFound** — not in this workspace |
| `qwen3-asr-flash-realtime` | Native DashScope WebSocket SDK | **ModelNotFound** — not in this workspace |
| `qwen3-asr-flash` | Native DashScope REST (async batch) | Reachable but requires Alibaba OSS audio URL + async callback webhook — unsuitable for real-time |
| All models | OpenAI-compat `/audio/transcriptions` | **404** — endpoint not exposed on this account |

### Speech Synthesis (TTS)
| Model | API | Status |
|---|---|---|
| `cosyvoice-v2` | Native DashScope WebSocket SDK | **ModelNotFound** — not in this workspace |
| `qwen3-tts-flash` | Native DashScope REST (async batch) | Reachable but requires async callback webhook — unsuitable for real-time |
| `qwen3-tts-instruct-flash` | Native DashScope REST (async batch) | Same |
| All models | OpenAI-compat `/audio/speech` | **404** — endpoint not exposed on this account |
| `qwen3-omni-flash` + `modalities:["audio"]` | OpenAI-compat | Accepted but returns `audio: null` — audio output not active for this account |

### Realtime / Streaming
| Endpoint | Status |
|---|---|
| OpenAI Realtime WebSocket `/compatible-mode/v1/realtime` | **404** — not exposed |
| `qwen3.5-omni-flash-realtime` via HTTP | Returns "current user api does not support http call" — WebSocket only, but WS endpoint is 404 |
| `qwen3-s2s-flash-realtime` | Internal server error |

---

## API Mapping Summary

| Capability | Correct API | Endpoint |
|---|---|---|
| Chat / agent reasoning | Native DashScope SDK (`dashscope.Generation`) | `https://dashscope-intl.aliyuncs.com/api/v1` |
| Embeddings | Native DashScope SDK (`dashscope.TextEmbedding`) | `https://dashscope-intl.aliyuncs.com/api/v1` |
| STT | **Browser Web Speech API** (`SpeechRecognition`) | Client-side only |
| TTS | **Browser SpeechSynthesis API** (`speechSynthesis`) | Client-side only |

---

## Voice Architecture Decision

### What was attempted
The original implementation used:
- `paraformer-realtime-v2` via DashScope SDK WebSocket for real-time ASR
- `cosyvoice-v2` via DashScope SDK streaming callback for TTS
- Binary PCM audio frames over WebSocket between browser and backend

### Why it didn't work
Both `paraformer-realtime-v2` and `cosyvoice-v2` return `ModelNotFound` for this
international DashScope workspace. The OpenAI-compatible audio endpoints
(`/audio/transcriptions`, `/audio/speech`) are not exposed. Async batch ASR/TTS
APIs require public callback URLs and are unsuitable for real-time conversation.

### Implemented solution
**Browser-native audio processing:**

```
Browser                          Backend (FastAPI)
──────                          ─────────────────
SpeechRecognition API ──────►  WS receives {type:"transcript", text}
(captures speech,               │
 sends final transcript)        ▼
                              Orchestrator (qwen-plus)
                                │
SpeechSynthesis API  ◄──────  WS sends {type:"reply_text", text}
(speaks reply)
```

**Benefits over server-side audio:**
- Zero latency for speech recognition (local, no round-trip)
- No API cost for audio processing
- Works on localhost without public URL
- Simpler, more reliable architecture

**Limitation:** Web Speech API requires Chrome or Edge. Firefox and Safari have
partial support. The chat text interface works in all browsers.

---

## Updated Configuration

`backend/app/core/config.py`:
```python
qwen_chat_model: str = "qwen-plus"       # confirmed available
qwen_embedding_model: str = "text-embedding-v3"  # confirmed available
# qwen_asr_model and qwen_tts_model removed — browser handles audio
```

`backend/.env`:
```
DASHSCOPE_BASE_URL=https://dashscope-intl.aliyuncs.com/api/v1
DASHSCOPE_COMPAT_URL=https://dashscope-intl.aliyuncs.com/compatible-mode/v1
QWEN_CHAT_MODEL=qwen-plus
QWEN_EMBEDDING_MODEL=text-embedding-v3
```

---

## Files Changed

| File | Change |
|---|---|
| `backend/app/main.py` | Added certifi SSL fix (macOS Homebrew Python 3.11) |
| `backend/app/services/qwen/client.py` | Added `base_websocket_api_url` derived from `DASHSCOPE_BASE_URL` |
| `backend/app/services/qwen/stt.py` | Replaced with stub — browser handles STT |
| `backend/app/services/qwen/tts.py` | Replaced with stub — browser handles TTS |
| `backend/app/api/v1/voice.py` | Rewritten: JSON text protocol instead of binary audio |
| `backend/app/core/config.py` | Removed ASR/TTS model settings; added `dashscope_compat_url` |
| `backend/.env` | Removed `QWEN_ASR_MODEL`, `QWEN_TTS_MODEL`, `QWEN_TTS_VOICE` |
| `frontend/components/VoiceButton.tsx` | Rewritten: Web Speech API + SpeechSynthesis |
