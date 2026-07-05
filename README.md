# BusinessPilot AI

A voice-first AI executive assistant for founders, freelancers, and small businesses —
powered entirely by **Qwen Cloud (DashScope)**. It plans, remembers, drafts, schedules,
and creates real business documents through natural conversation (typed or spoken),
while keeping a human in the loop for anything with a real-world side effect (sending
email, creating calendar events).

## Architecture

```
frontend/   Next.js (App Router, TypeScript, Tailwind) -- pure API/WebSocket consumer.
            No AI logic lives here; it only renders what the backend returns.

backend/    FastAPI, fully async (SQLAlchemy 2.0 + SQLite now, Postgres-ready).
            app/agents/      Planner, Memory, Research, Document, Email, Calendar,
                              Marketing, Reviewer agents + the Orchestrator that wires
                              them together. Used by BOTH the text /chat endpoint and
                              the /voice WebSocket -- one pipeline, two input modes.
            app/services/    Qwen client (chat/embeddings/STT/TTS), memory, documents,
                              Google OAuth + Gmail + Calendar, notifications, scheduler.
            app/api/v1/      REST + WebSocket routes.
            app/db/          SQLAlchemy models + Alembic migrations.
```

**Approval gating is structural, not just prompted.** The `send_email` and
`create_calendar_event` tools never call the real Gmail/Calendar API directly. Agents
can only create a `pending_approval` draft row; a separate `/approve` endpoint is the
only code path that ever touches the live Google API. This holds even if the model
misbehaves.

## Prerequisites

- Python 3.11+ (3.14 currently lacks prebuilt wheels for several pinned deps -- use 3.11)
- Node.js 20.9+
- A DashScope (Qwen Cloud) API key
- (Optional, for Email/Calendar features) a Google Cloud OAuth client

## Backend setup

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt   # or requirements.txt for prod-only deps

cp .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(48))"        # -> SECRET_KEY
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"  # -> ENCRYPTION_KEY
# paste both into .env, plus your QWEN_API_KEY (already pre-filled if you provided one)

alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

Swagger UI: http://localhost:8000/api/v1/docs

Run the test suite (Qwen/Google calls are mocked, no live API spend):

```bash
python -m pytest -q
```

### Qwen Cloud (DashScope) configuration

`backend/.env`:

| Variable | Purpose |
|---|---|
| `QWEN_API_KEY` | Your DashScope API key |
| `DASHSCOPE_BASE_URL` | `https://dashscope-intl.aliyuncs.com/api/v1` (international) or `https://dashscope.aliyuncs.com/api/v1` (China) -- must match the region your key was issued in |
| `QWEN_CHAT_MODEL` | Default `qwen-plus` (qwen3-plus class) for all agent reasoning |
| `QWEN_EMBEDDING_MODEL` | Default `text-embedding-v3` for memory vectors |
| `DASHSCOPE_COMPAT_URL` | OpenAI-compatible endpoint used by the chat client |

> **Note on STT/TTS:** Server-side ASR and TTS (paraformer, cosyvoice) are not
> available on the DashScope international workspace. Voice I/O is handled entirely
> by the browser's Web Speech API — no server-side ASR/TTS configuration is needed.

### Google OAuth (Gmail + Calendar) configuration

1. In [Google Cloud Console](https://console.cloud.google.com/), create a project and enable the **Gmail API** and **Google Calendar API**.
2. Create an **OAuth 2.0 Client ID** (type: Web application).
3. Add an authorized redirect URI matching `GOOGLE_REDIRECT_URI` in `.env` (default `http://localhost:8000/api/v1/integrations/google/callback`).
4. Copy the client ID/secret into `backend/.env` as `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET`.
5. In the app, go to **Settings → Connect Google account**. Without this, the Email and Calendar agents will respond that the account isn't connected, but everything else works fine.

## Frontend setup

```bash
cd frontend
npm install
cp .env.local.example .env.local   # NEXT_PUBLIC_API_URL defaults to http://localhost:8000
npm run dev
```

Open http://localhost:3000. Sign up, then try in Chat:

- "Write me a one-page business plan for my coffee shop."
- "Draft a follow-up email to a client about a delayed delivery."
- "Propose a meeting with my co-founder next week."

Type-check / lint / production build:

```bash
npx tsc --noEmit
npx eslint .
npm run build
```

## Running with Docker

```bash
docker compose up --build
```

This builds both services from their own `Dockerfile`s (`backend/Dockerfile` runs
Alembic migrations on boot; `frontend/Dockerfile` is a multi-stage Next.js
`output: "standalone"` build) and serves the backend on `:8000` and frontend on
`:3000`. Set `NEXT_PUBLIC_API_URL` in your shell before `docker compose up` if the
frontend needs to reach the backend at a non-default URL (it's a build-time value,
baked into the client bundle).

## Deploying to Alibaba Cloud

Only the **backend** is deployed as a Docker image. The frontend is a separate
client application and is **not** included in the backend build — deploy it
independently (Vercel, CDN, a second ECS instance, or another container).

### 1 — Prerequisites

- Docker installed locally and on the target server
- An **Alibaba Cloud** account with:
  - **ACR** (Container Registry) namespace created
  - An **ECS** instance (or ECI/ACK) to run the container
  - (Recommended) **ApsaraDB RDS for PostgreSQL** when you outgrow SQLite

### 2 — Build and push the backend image

The build context is `./backend/` only — the frontend directory is never included.

```bash
# Authenticate with ACR once
docker login registry.cn-<region>.aliyuncs.com \
  -u <ram-user> -p <ram-password>

# Build and push (uses git SHA as the tag for traceability)
export ACR_REGISTRY=registry.cn-<region>.aliyuncs.com
export ACR_NAMESPACE=<your-namespace>
export IMAGE_TAG=$(git rev-parse --short HEAD)

./scripts/push-to-acr.sh
```

The script builds from `./backend`, tags the image as
`${ACR_REGISTRY}/${ACR_NAMESPACE}/businesspilot-api:<tag>`, and pushes both the
versioned tag and `:latest`.

### 3 — Prepare the server environment

SSH into the ECS instance and create the production env file:

```bash
# Install Docker + Compose plugin if not already present
curl -fsSL https://get.docker.com | sh
apt-get install -y docker-compose-plugin   # Ubuntu/Debian

# Clone only the compose file, or copy it manually
scp docker-compose.prod.yml user@<ecs-ip>:/opt/businesspilot/
scp backend/.env.example     user@<ecs-ip>:/opt/businesspilot/.env.prod

# Edit .env.prod with real values (see section 4 below)
ssh user@<ecs-ip> "nano /opt/businesspilot/.env.prod"
```

The server needs only `docker-compose.prod.yml` and `.env.prod` — no source code.

### 4 — Required environment variables (`.env.prod`)

Start from `backend/.env.example`. The following must have real values in production:

| Variable | How to generate / where to get it |
|---|---|
| `ENVIRONMENT` | Set to `production` |
| `DEBUG` | Set to `false` |
| `SECRET_KEY` | `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `ENCRYPTION_KEY` | `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `DATABASE_URL` | `postgresql+asyncpg://user:pass@<rds-host>:5432/businesspilot` |
| `QWEN_API_KEY` | Your DashScope key |
| `GOOGLE_CLIENT_ID` | From Google Cloud Console OAuth credentials |
| `GOOGLE_CLIENT_SECRET` | From Google Cloud Console OAuth credentials |
| `GOOGLE_REDIRECT_URI` | `https://<your-api-domain>/api/v1/integrations/google/callback` |
| `FRONTEND_ORIGIN` | `https://<your-frontend-domain>` (CORS allow-list) |

> **Never** commit `.env.prod` to source control. For secrets management at scale, use
> Alibaba Cloud **KMS** or store the values in the ACK/ECI environment configuration.

### 5 — Run the backend

```bash
ssh user@<ecs-ip>
cd /opt/businesspilot

# Pull the new image and restart
export ACR_IMAGE=registry.cn-<region>.aliyuncs.com/<namespace>/businesspilot-api:<tag>
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d

# Database migrations run automatically on every container start (alembic upgrade head).
# Verify the container is healthy:
docker compose -f docker-compose.prod.yml ps
curl http://localhost:8000/health
```

### 6 — Networking and HTTPS

Put the backend behind **Alibaba Cloud SLB** (Server Load Balancer) or an
**Nginx/Caddy** sidecar for HTTPS termination:

```nginx
server {
    listen 443 ssl;
    server_name api.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;   # required for WebSocket (/ws/*)
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### 7 — Upgrading

```bash
# On your local machine
export IMAGE_TAG=$(git rev-parse --short HEAD)
./scripts/push-to-acr.sh

# On the server
export ACR_IMAGE=registry.cn-<region>.aliyuncs.com/<namespace>/businesspilot-api:${IMAGE_TAG}
docker compose -f docker-compose.prod.yml pull && \
docker compose -f docker-compose.prod.yml up -d
```

Database migrations run automatically when the new container starts.

### 8 — Scaling beyond a single instance

| Concern | Solution |
|---|---|
| Database | Switch `DATABASE_URL` to **ApsaraDB RDS for PostgreSQL** — no code changes needed |
| File storage | Swap `LocalStorageBackend` for an **OSS-backed** implementation in `app/services/storage_service.py` |
| Multiple API replicas | Deploy to **ACK** (Kubernetes); the SQLite → Postgres switch is required first |
| Secrets at scale | Store values in Alibaba Cloud **KMS** and inject via ACK Secret objects |

## Known limitations (by design, for this v1)

- **Research Agent** uses Qwen's own knowledge, not live web browsing -- it's
  explicit in its output when it isn't confident about a current/live fact.
- **Single Google account per user**, Gmail + Calendar only (no Outlook in v1).
- **SQLite by default** -- fine for a single-instance deployment; see the Postgres
  migration note above when you need to scale.
