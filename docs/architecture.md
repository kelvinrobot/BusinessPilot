# BusinessPilot AI — Architecture Notes

## Request flow

```
Browser (Next.js)
  │
  ├─ REST (fetch + Authorization: Bearer)  ─────► FastAPI /api/v1/*
  │                                                  │
  └─ WebSocket (auth via first message)    ─────► /voice/ws
                                                   /notifications/ws
```

## Agent pipeline

Every user message — typed or spoken — enters the same pipeline:

```
Orchestrator
  ├─ PlannerAgent      decides which specialist agents to call
  ├─ [specialist agents run in sequence]
  │    MemoryAgent     injects relevant long-term facts
  │    ResearchAgent   answers factual questions from model knowledge
  │    DocumentAgent   generates .docx / .pdf files
  │    EmailAgent      creates pending-approval email drafts
  │    CalendarAgent   creates pending-approval calendar event drafts
  │    MarketingAgent  writes copy, social posts, ad text
  └─ ReviewerAgent     checks output quality (one retry if needed)
```

Approval gating is **structural**: `EmailAgent` and `CalendarAgent` only write a
`status=pending_approval` row to the database. The live Gmail / Calendar API is called
exclusively from the `/email/drafts/{id}/approve` and `/calendar/events/{id}/approve`
endpoints, after explicit user action.

## Key technology decisions

| Concern | Choice | Rationale |
|---|---|---|
| AI backbone | Qwen Cloud (DashScope) | Only provider available to the user; `qwen-plus` covers chat+tools |
| Embeddings | `text-embedding-v3` | Available on the international workspace; 1536-dim vectors |
| STT / TTS | Browser Web Speech API | Server-side ASR/TTS (paraformer, cosyvoice) unavailable on international workspace |
| Database | SQLite → PostgreSQL-ready | Start simple; single `DATABASE_URL` change moves to Postgres |
| Auth | JWT (access + refresh, rotate-on-use) | Stateless, works behind any load balancer |
| OAuth token storage | Fernet-encrypted in DB | Tokens at rest are ciphertext; key lives in `ENCRYPTION_KEY` |
| Async runtime | FastAPI + SQLAlchemy 2.0 async | Fully non-blocking; all DB and HTTP calls are async |

## WebSocket authentication protocol

Tokens are **not** placed in the URL query string (they would appear in server access
logs). Instead:

1. Client opens `ws://…/voice/ws` (no token in URL)
2. Client immediately sends `{"type": "auth", "token": "<access_token>"}`
3. Server validates within 10 seconds; closes `4401` if invalid or absent
4. Normal message exchange begins

Both `/voice/ws` and `/notifications/ws` use this protocol.

## Directory map

```
backend/
  app/
    agents/        Planner, Memory, Research, Document, Email,
                   Calendar, Marketing, Reviewer, Orchestrator
    api/v1/        FastAPI routers (auth, chat, voice, email,
                   calendar, documents, tasks, memory,
                   notifications, integrations)
    core/          config, exceptions, logging, security, rate_limit
    db/            SQLAlchemy models + Alembic migrations
    repositories/  Thin async data-access layer (one per model)
    schemas/       Pydantic request/response models
    services/      Qwen client, email, calendar, OAuth,
                   memory, documents, storage, scheduler,
                   notifications
    websocket/     ConnectionManager (voice + notifications)
  alembic/         Migration versions
  tests/           pytest-asyncio integration tests
  Dockerfile
  requirements.txt

frontend/
  app/             Next.js App Router pages
  components/      AppShell, AuthProvider, VoiceButton,
                   NotificationBell, ProtectedRoute
  lib/             api.ts, auth.ts, types.ts, useNotifications.ts
  Dockerfile

docker-compose.yml       Development (builds both services)
docker-compose.prod.yml  Production (backend image only, pulled from ACR)
scripts/push-to-acr.sh   Build + push backend image to Alibaba ACR
```
