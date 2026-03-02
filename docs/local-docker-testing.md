# 🐳 Local Docker Testing Guide

Test the full Docker stack locally before deploying to production.

---

## 📋 Overview

This guide covers running **IAM-Dynamic** locally using Docker Compose on your development machine. Perfect for testing changes before pushing to production.

**Supported Platforms:**
- 🪟 **Windows 11** with Docker Desktop + WSL 2
- 🍎 **macOS** (Apple Silicon and Intel)
- 🐧 **Linux** (Ubuntu, Fedora, etc.)

---

## 🎯 Prerequisites

### Windows 11
| Requirement | Details |
|-------------|---------|
| Docker Desktop | [Download here](https://docs.docker.com/desktop/install/windows-install/) |
| WSL 2 | Enabled automatically by Docker Desktop |
| Terminal | Git Bash, PowerShell, or Windows Terminal |

### macOS (Apple Silicon & Intel)
| Requirement | Details |
|-------------|---------|
| Docker Desktop | [Download for Mac](https://docs.docker.com/desktop/install/mac-install/) |
| Architecture | Supports both Apple Silicon (M1/M2/M3) and Intel |

### Linux (Ubuntu/Fedora/etc.)
| Requirement | Details |
|-------------|---------|
| Docker Engine | [Install guide](https://docs.docker.com/engine/install/) |
| Docker Compose | Included with modern Docker Engine |

**Verify Docker is working:**

```bash
docker --version
docker compose version
```

---

## ⚙️ Step 1: Create Your `.env` File

If you don't already have one in the project root:

```bash
# Copy example if it exists
cp .env.example .env

# Or create manually
nano .env
```

### Minimum Required Variables

```env
# AI Provider
LLM_PROVIDER=gemini
GOOGLE_API_KEY=AIzaSy...

# AWS Configuration
AWS_ACCOUNT_ID=123456789012
AWS_ROLE_NAME=AgentPOCSessionRole

# Optional
APPROVER_NAME=Admin
```

### Add Additional Providers (Optional)

```env
# OpenAI
# OPENAI_API_KEY=sk-...
# OPENAI_MODEL=gpt-5.1

# Anthropic Claude
# ANTHROPIC_API_KEY=sk-ant-...
# ANTHROPIC_MODEL=claude-opus-4-5-20251101

# Zhipu GLM
# ZHIPUAI_API_KEY=...
# ZHIPUAI_MODEL=glm-4.7

# AWS Credentials (for credential issuance)
# AWS_ACCESS_KEY_ID=AKIA...
# AWS_SECRET_ACCESS_KEY=...
# AWS_DEFAULT_REGION=us-east-1
```

See [`CLAUDE.md`](../CLAUDE.md) for the complete configuration reference.

---

## 🔐 Optional: Enable Authentication Locally

By default, authentication is **disabled** in local dev (no login page). To test the login flow locally, use the setup script:

```bash
bash setup-auth.sh --dev
```

This prompts for:
- Username and password
- Generates bcrypt hash automatically
- Generates JWT secret
- Skips Turnstile and Caddy steps (dev only)

### Manual Auth Setup

Alternatively, set the values manually:

```env
AUTH_USERNAME=admin
AUTH_PASSWORD_HASH=$2b$12$...   # Generate with: python backend/scripts/hash_password.py
JWT_SECRET=dev-secret-at-least-32-characters-long
```

**Generate password hash:**

```bash
pip install passlib[bcrypt]
python backend/scripts/hash_password.py
```

---

## 🚀 Step 2: Build and Start

### Start All Services

```bash
docker compose up --build
```

This builds both images from scratch and starts the containers.

| Metric | Time |
|--------|------|
| First build | 2-3 minutes |
| Subsequent builds | 10-30 seconds (uses cache) |

You'll see logs from both `frontend` and `backend` in the terminal.

### Run in Background

```bash
docker compose up --build -d
```

View logs separately:

```bash
docker compose logs -f           # All services
docker compose logs -f backend   # Backend only
docker compose logs -f frontend  # Frontend only
```

---

## ✅ Step 3: Verify Everything Works

### Health Checks

```bash
# Frontend (nginx health endpoint)
curl http://localhost:8080/nginx-health

# Backend proxied through nginx
curl http://localhost:8080/health

# Backend direct (bypasses nginx)
curl http://localhost:8000/health
```

**On Windows without `curl`:**

```powershell
Invoke-WebRequest http://localhost:8080/nginx-health
Invoke-WebRequest http://localhost:8080/health
```

### Application URLs

| URL | Description |
|-----|-------------|
| http://localhost:8080 | Full app (frontend + API via nginx proxy) |
| http://localhost:8080/docs | Swagger API docs (proxied to backend) |
| http://localhost:8000/docs | Swagger API docs (direct to backend) |

### Container Status

```bash
docker compose ps
```

**Expected output:**

```
NAME                IMAGE                      STATUS
iam-frontend-1      ghcr.io/.../frontend      Up (healthy)
iam-backend-1       ghcr.io/.../backend       Up (healthy)
```

---

## 🧪 Step 4: Test the Full Flow

1. **Open** http://localhost:8080 in your browser
2. **Enter** an access request (e.g., "Read-only access to S3 bucket my-data-bucket")
3. **Select** an LLM provider and duration
4. **Submit** and review the generated policy
5. **Approve** or reject

If you have AWS credentials configured, approving will issue temporary STS credentials.

---

## 💻 Step 5: Development Mode

The `docker-compose.yml` mounts `./backend` as a volume with `--reload`, so backend code changes are picked up automatically without rebuilding.

### Frontend Development

For frontend changes, rebuild the frontend:

```bash
docker compose up --build frontend
```

### Hybrid Mode (Recommended for Active Development)

Run the backend via Docker and frontend via Vite:

```bash
# Terminal 1: Backend via Docker (with hot reload)
docker compose up backend

# Terminal 2: Frontend via Vite
cd frontend
npm install
npm run dev
```

The Vite dev server at http://localhost:3000 proxies API calls to http://localhost:8000 automatically (configured in `vite.config.ts`).

---

## 🛠️ Step 6: Useful Commands

| Command | Description |
|---------|-------------|
| `docker compose down` | Stop all containers |
| `docker compose down --rmi local --volumes` | Stop and remove volumes/images |
| `docker compose build backend` | Rebuild backend image |
| `docker compose build frontend` | Rebuild frontend image |
| `docker compose restart backend` | Restart backend service |
| `docker compose exec backend bash` | Shell into backend container |
| `docker compose exec frontend sh` | Shell into frontend container |
| `docker stats` | View resource usage |

---

## 🔧 Troubleshooting

### Port Already in Use

```
Error: bind: address already in use
```

**Find and stop the conflicting process:**

```bash
# macOS/Linux
lsof -i :8080
lsof -i :8000

# Windows (PowerShell)
netstat -ano | findstr :8080
netstat -ano | findstr :8000
```

**Or change the port mapping** in `docker-compose.yml`:

```yaml
services:
  frontend:
    ports:
      - "9090:8080"  # Access at localhost:9090 instead
```

### Frontend Shows Blank Page

**Check the browser console** for errors. Common cause: backend isn't healthy yet.

```bash
docker compose logs backend
```

### Backend Won't Start

**Check for missing environment variables:**

```bash
docker compose logs backend
```

**Common issues:**
| Issue | Solution |
|-------|----------|
| Missing `.env` file | Create `.env` with required variables |
| Invalid API keys | Verify keys are correct and active |
| Python import errors | Check `requirements.txt` is complete |

### M3/Mac Platform Warning

If you see:

```
WARNING: The requested image's platform (linux/amd64)
does not match the detected host platform (linux/arm64/v8)
```

Both Dockerfiles use multi-arch base images, so this shouldn't happen. If it does, add to `docker-compose.yml`:

```yaml
services:
  backend:
    platform: linux/arm64
  frontend:
    platform: linux/arm64
```

### Nuclear Option: Rebuild from Scratch

```bash
docker compose down --rmi local --volumes
docker builder prune -f
docker compose up --build
```

---

## 📚 Additional Resources

- [Antsle Deployment Guide](antsle-deployment-guide.md) 🐜
- [VPS Deployment Guide](vps-setup-guide.md) 🌐
- [MicroK8s ArgoCD Guide](microk8s-argocd-deployment-guide.md) ☸️
- [CLAUDE.md](../CLAUDE.md) - Project documentation

---

**Happy testing! 🎉**
