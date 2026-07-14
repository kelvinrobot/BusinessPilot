# Alibaba Cloud Deployment

BusinessPilot AI's backend runs in production on an **Alibaba Cloud Elastic Compute Service (ECS)** Ubuntu instance, behind Nginx and HTTPS. The frontend is deployed separately on Vercel and talks to the ECS instance over HTTPS/WSS.

```
                      +----------------------------+
                      |        User Browser        |
                      +--------------+-------------+
                                     |
                                     | HTTPS
                                     v
                      +----------------------------+
                      |      Vercel Frontend        |
                      |         (Next.js)           |
                      +--------------+-------------+
                                     |
                                     | HTTPS / WSS
                                     v
   +-----------------------------------------------------------------+
   |            Alibaba Cloud ECS — Ubuntu (production host)         |
   |                                                                  |
   |   +-------------------+     +--------------------------------+  |
   |   |  Nginx (443/80)   | --> |   Docker container: businesspilot|  |
   |   |  reverse proxy +  |     |   FastAPI + Uvicorn  :8000       |  |
   |   |  TLS termination  |     |   (alembic migrations on boot)   |  |
   |   +-------------------+     +----------------+-----------------+  |
   |          ^                                    |                  |
   |          | Let's Encrypt / Certbot             |                  |
   |          |                                     |                  |
   +----------+-------------------------------------+------------------+
              |                                      |
      DuckDNS (dynamic DNS)                          |
                                       +--------------+---------------+
                                       |                              |
                                       v                              v
                              Qwen Cloud (DashScope)          Google Workspace APIs
                              qwen-plus / text-embedding-v3   Gmail + Calendar
```

## Infrastructure

| Component | Choice |
|---|---|
| Cloud provider | Alibaba Cloud |
| Compute | Elastic Compute Service (ECS) |
| Operating system | Ubuntu |
| Container runtime | Docker |
| Reverse proxy | Nginx |
| TLS / HTTPS | Let's Encrypt (Certbot) |
| DNS | DuckDNS |
| AI backbone | Qwen Cloud / DashScope (`qwen-plus`, `text-embedding-v3`) |
| External integrations | Google Gmail API, Google Calendar API |

## Deployment Process

### 1. Provision the ECS instance

An Ubuntu ECS instance is provisioned in the Alibaba Cloud console, with a security group opening inbound TCP `22` (SSH), `80` (HTTP, for Certbot's ACME challenge), and `443` (HTTPS). Docker and Nginx are installed on first boot:

```bash
sudo apt-get update
sudo apt-get install -y docker.io nginx certbot python3-certbot-nginx
sudo systemctl enable docker nginx
```

### 2. Point DNS at the instance

A DuckDNS subdomain is configured to resolve to the ECS instance's public IP, so the box has a stable hostname for Certbot to issue a certificate against instead of a bare IP address.

### 3. Clone the repository

```bash
git clone https://github.com/kelvinrobot/BusinessPilot.git
cd BusinessPilot/backend
```

### 4. Configure the environment

```bash
cp .env.example .env
nano .env
```

`.env` is filled in with production values for the variables defined in [`backend/.env.example`](../backend/.env.example), most importantly:

| Variable | Purpose |
|---|---|
| `ENVIRONMENT=production`, `DEBUG=false` | Disables dev-only behavior |
| `QWEN_API_KEY` | DashScope API key used for all Qwen chat/embedding calls |
| `DASHSCOPE_BASE_URL` / `DASHSCOPE_COMPAT_URL` | International DashScope endpoints |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` / `GOOGLE_REDIRECT_URI` | Google OAuth app credentials, redirect URI updated to the production domain |
| `FRONTEND_ORIGIN` | Locked to the Vercel production URL (CORS + OAuth redirect allow-list) |
| `SECRET_KEY` | JWT signing key, generated with `secrets.token_urlsafe(48)` |
| `ENCRYPTION_KEY` | Fernet key encrypting stored Google OAuth tokens at rest |
| `DATABASE_URL` | Points at the production database |

### 5. Build the Docker image

```bash
docker build -t businesspilot-api .
```

The [`Dockerfile`](../backend/Dockerfile) builds a slim Python 3.11 image, installs dependencies, and runs as a non-root `appuser`. Its entrypoint runs pending Alembic migrations before starting Uvicorn, so every deploy self-migrates the database:

```dockerfile
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
```

### 6. Run the container

```bash
docker run -d \
  --name businesspilot \
  --restart unless-stopped \
  --env-file .env \
  -p 8000:8000 \
  businesspilot-api
```

`--restart unless-stopped` means the container survives an ECS reboot without manual intervention.

### 7. Configure Nginx as a reverse proxy

Nginx terminates TLS and forwards traffic to the container on `127.0.0.1:8000`, with the `Upgrade`/`Connection` headers needed for the app's WebSocket endpoints (`/voice/ws`, `/notifications/ws`):

```nginx
server {
    listen 80;
    server_name <duckdns-subdomain>.duckdns.org;

    location / {
        proxy_pass http://127.0.0.1:8000;

        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 8. Issue an HTTPS certificate

```bash
sudo certbot --nginx -d <duckdns-subdomain>.duckdns.org
```

Certbot rewrites the Nginx server block to redirect port 80 to 443 and installs a Let's Encrypt certificate. Renewal is handled automatically by Certbot's systemd timer (`certbot renew` runs twice daily, only renewing certs within 30 days of expiry).

### 9. Verify the deployment

The API exposes a `/health` endpoint (`backend/app/main.py`) used to confirm the container and reverse proxy are both up:

```bash
curl https://<duckdns-subdomain>.duckdns.org/health
```

### 10. Redeploying

A code change is shipped by pulling the latest commit, rebuilding the image, and replacing the running container:

```bash
git pull origin main
docker build -t businesspilot-api .
docker stop businesspilot && docker rm businesspilot
docker run -d \
  --name businesspilot \
  --restart unless-stopped \
  --env-file .env \
  -p 8000:8000 \
  businesspilot-api
```

Because migrations run as part of the container's `CMD`, schema changes apply automatically on the next start — no separate migration step is needed.

## Production Architecture Summary

```
User → Vercel Frontend → HTTPS → Alibaba Cloud ECS → Nginx (TLS) → Docker → FastAPI → Qwen Cloud / Google Workspace APIs
```

BusinessPilot AI's backend is currently running in production on Alibaba Cloud ECS, fronted by Nginx over HTTPS, with the frontend served separately from Vercel.
