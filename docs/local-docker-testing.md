# Local Docker Testing Guide

Test the full Docker stack locally before deploying to your VPS.

---

## Prerequisites

### Windows 11
- **Docker Desktop** installed and running (https://docs.docker.com/desktop/install/windows-install/)
- WSL 2 backend enabled (Docker Desktop will prompt you)
- Git Bash or terminal of choice

### macOS (MacBook Air M3)
- **Docker Desktop for Mac (Apple Silicon)** installed and running (https://docs.docker.com/desktop/install/mac-install/)
- Terminal

Verify Docker is working on either platform:

```bash
docker --version
docker compose version
```

---

## 1. Create Your `.env` File

If you don't already have one in the project root:

```bash
cp .env.example .env   # if .env.example exists, otherwise create manually
```

At minimum you need:

```env
LLM_PROVIDER=gemini
GOOGLE_API_KEY=AIzaSy...

AWS_ACCOUNT_ID=123456789012
AWS_ROLE_NAME=AgentPOCSessionRole

APPROVER_NAME=Admin
```

Add any additional provider keys (OpenAI, Anthropic, Zhipu) or AWS credentials as needed. See `CLAUDE.md` for the full list.

### Optional: Enable Authentication Locally

By default, authentication is **disabled** in local dev (no login page). To test the login flow locally, use the setup script:

```bash
bash setup-auth.sh --dev
```

This prompts for a username/password, generates the bcrypt hash and JWT secret, and writes them to `.env`. Turnstile and Caddy steps are skipped in `--dev` mode.

Alternatively, you can set the values manually:

```env
AUTH_USERNAME=admin
AUTH_PASSWORD_HASH=$2b$12$...   # Generate with: python backend/scripts/hash_password.py
JWT_SECRET=dev-secret-at-least-32-characters-long
```

To generate the password hash manually:

```bash
pip install passlib[bcrypt]
python backend/scripts/hash_password.py
```

---

## 2. Build and Start

```bash
docker compose up --build
```

This builds both images from scratch and starts the containers. First build takes 2-3 minutes; subsequent builds use cache and are much faster.

You'll see logs from both `frontend` and `backend` in the terminal.

### Run in Background

```bash
docker compose up --build -d
```

Then view logs separately:

```bash
docker compose logs -f           # all services
docker compose logs -f backend   # backend only
docker compose logs -f frontend  # frontend only
```

---

## 3. Verify Everything Works

### Health checks

```bash
# Frontend (nginx)
curl http://localhost:8080/nginx-health

# Backend (FastAPI) proxied through nginx
curl http://localhost:8080/health

# Backend direct (bypasses nginx)
curl http://localhost:8000/health
```

On Windows without `curl`, open these URLs in your browser or use PowerShell:

```powershell
Invoke-WebRequest http://localhost:8080/nginx-health
Invoke-WebRequest http://localhost:8080/health
```

### Application URLs

| URL | What |
|-----|------|
| http://localhost:8080 | Full app (frontend + API via nginx proxy) |
| http://localhost:8080/docs | Swagger API docs (proxied to backend) |
| http://localhost:8000/docs | Swagger API docs (direct to backend) |

### Container status

```bash
docker compose ps
```

You should see both `frontend` and `backend` with status `Up` and `(healthy)`.

---

## 4. Test the Full Flow

1. Open http://localhost:8080 in your browser
2. Enter an access request (e.g., "Read-only access to S3 bucket my-data-bucket")
3. Select an LLM provider and duration
4. Submit and review the generated policy
5. Approve or reject

If you have AWS credentials configured, approving will issue temporary STS credentials.

---

## 5. Development Mode

The `docker-compose.yml` mounts `./backend` as a volume with `--reload`, so backend code changes are picked up automatically without rebuilding.

For frontend changes, you need to rebuild since nginx serves the compiled static files:

```bash
docker compose up --build frontend
```

Alternatively, for active frontend development, run the Vite dev server natively alongside the Docker backend:

```bash
# Terminal 1: backend via Docker
docker compose up backend

# Terminal 2: frontend via Vite (with hot reload)
cd frontend
npm install
npm run dev
```

The Vite dev server at http://localhost:3000 proxies API calls to http://localhost:8000 automatically (configured in `vite.config.ts`).

---

## 6. Useful Commands

```bash
# Stop everything
docker compose down

# Stop and remove volumes/images
docker compose down --rmi local --volumes

# Rebuild a single service
docker compose build backend
docker compose build frontend

# Restart a single service
docker compose restart backend

# Shell into a running container
docker compose exec backend bash
docker compose exec frontend sh    # alpine uses sh, not bash

# Check resource usage
docker stats
```

---

## 7. Troubleshooting

### Port already in use
```
Error: bind: address already in use
```

Something else is using port 8080 or 8000. Find and stop it:

```bash
# macOS/Linux
lsof -i :8080
lsof -i :8000

# Windows (PowerShell)
netstat -ano | findstr :8080
netstat -ano | findstr :8000
```

Or change the port mapping in `docker-compose.yml`:
```yaml
ports:
  - "9090:8080"  # access at localhost:9090 instead
```

### Frontend shows blank page
Check the browser console for errors. Common cause: backend isn't healthy yet. The frontend container waits for the backend health check (`depends_on: condition: service_healthy`), but if the backend fails to start, the frontend won't proxy API calls correctly.

```bash
docker compose logs backend
```

### Backend won't start
Check for missing environment variables:

```bash
docker compose logs backend
```

Common issues:
- Missing `.env` file
- Invalid API keys
- Python import errors (check `requirements.txt` is complete)

### M3 Mac: platform warning
If you see `WARNING: The requested image's platform (linux/amd64) does not match the detected host platform (linux/arm64/v8)`:

Both Dockerfiles use multi-arch base images (`node:20-alpine`, `python:3.11-slim`, `nginx:1.27-alpine`), so this shouldn't happen. If it does, add to `docker-compose.yml`:

```yaml
services:
  backend:
    platform: linux/arm64
  frontend:
    platform: linux/arm64
```

### Rebuild from scratch (nuclear option)
```bash
docker compose down --rmi local --volumes
docker builder prune -f
docker compose up --build
```
