# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**IAM-Dynamic** is an AI-driven Just-In-Time AWS IAM access request portal. It uses multiple LLM providers (Google Gemini, OpenAI, Anthropic Claude, Z.AI GLM) to generate least-privilege IAM policies from natural language requests, then issues temporary credentials via AWS STS.

## Architecture

### Modern React/FastAPI Architecture (v3.0+)

The application uses a modern frontend/backend separation pattern:

- **Frontend (`frontend/`)**: React SPA with TypeScript, Vite, and Tailwind CSS
  - Multi-view state machine (request → review → credentials/rejected)
  - System theme detection and toggle (light/dark/system)
  - LLM provider/model selector with real-time switching
  - Markdown-formatted AI guidance with syntax highlighting
  - Multiple credential export formats (Bash, PowerShell, AWS CLI)

- **Backend (`backend/`)**: FastAPI REST API
  - Multi-provider LLM support (Gemini, OpenAI, Anthropic, Z.AI)
  - Policy generation and validation endpoints
  - Credential issuance via AWS STS AssumeRole
  - Rejection guidance with AI-powered suggestions
  - JWT authentication with bcrypt password hashing (optional, enabled via env vars)
  - Cloudflare Turnstile CAPTCHA verification (optional)
  - Comprehensive error handling and logging
  - OpenAPI documentation at `/docs`

### LLM Service Layer

The backend uses a Strategy Pattern ([`backend/llm_service.py`](backend/llm_service.py)) to support multiple AI providers:

- **`LLMProvider`** (ABC): Abstract base class defining `generate_policy(request_text: str) -> PolicyResponse`
- **`GeminiProvider`**: Default engine using `google.genai` with Gemini 3.1 Pro Preview
- **`OpenAIProvider`**: OpenAI GPT-5.3
- **`AnthropicProvider`**: Anthropic Claude Opus 4.6
- **`ZhipuProvider`**: Z.AI GLM-5.1 (global platform via api.z.ai)

The provider is selected via `LLM_PROVIDER` environment variable (`gemini`, `openai`, `claude`, or `zhipu`).

### Data Flow

```
User Request (React UI)
        ↓
FastAPI POST /api/generate-policy
        ↓
LLMProvider.generate_policy() → PolicyResponse
        ↓
{policy, risk, explanation, approver_note}
        ↓
Risk-based auto-approval OR manual approval
        ↓
FastAPI POST /api/issue-credentials
        ↓
boto3 sts.assume_role() → Credentials
        ↓
Display + Slack audit log
```

### Application Entry Points

1. **Frontend**: `frontend/src/App.tsx`
   - Main React application with view routing
   - Auth gate: shows LoginView when auth is required and user is not authenticated
   - Views: login, request, review, credentials, rejected

2. **Backend**: `backend/main.py`
   - FastAPI application with API endpoints
   - Health check, auth (login/verify), provider config, policy generation, credential issuance, rejection guidance
   - `get_current_user` dependency protects all endpoints except health and auth

### Backend Services

- **`backend/services/sts_service.py`**: AWS STS AssumeRole with session policies
- **`backend/services/slack_service.py`**: Webhook notifications for audit trail
- **`backend/services/auth_service.py`**: JWT creation/verification, bcrypt password checking
- **`backend/services/turnstile_service.py`**: Cloudflare Turnstile CAPTCHA verification

## Running the Application

### Local Development (without Docker)

```bash
# Setup
python3 -m venv venv
source venv/bin/activate  # venv\bin\activate on Windows
pip install -r backend/requirements.txt

# Start Backend
cd backend
python main.py
# Or: uvicorn main:app --reload --port 8000

# Start Frontend (new terminal)
cd frontend
npm install
npm run dev
# Or: npm run build && npm run preview
```

**Development script:**
```bash
./start-dev.sh  # Starts both backend and frontend
```

**Access URLs:**
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

### Docker Development

```bash
docker compose up --build        # Build and run both containers
docker compose up --build -d     # Detached mode
docker compose down              # Stop and remove containers
```

**Access URL:** http://localhost:8080 (nginx serves frontend + proxies API to backend)

### Docker Production

```bash
docker compose -f docker-compose.prod.yml up -d
```

Uses pre-built images from `ghcr.io/tupacalypse187/iam-dynamic-*`.

## Docker Architecture

### Development (docker-compose.yml)

Two-container setup, ports exposed for local access:

| Service | Base Image | Port | Role |
|---------|-----------|------|------|
| `frontend` | `nginx:1.27-alpine` | 8080 | Serves React SPA, reverse-proxies `/api`, `/health`, `/config`, `/docs` to backend |
| `backend` | `python:3.11-slim` | 8000 | FastAPI + uvicorn with 2 workers |

### Production (docker-compose.prod.yml)

Three-container setup with Caddy for TLS termination:

```
Internet → Caddy (443, TLS via Cloudflare DNS) → nginx frontend (8080, internal) → backend (8000, internal)
```

| Service | Base Image | Port | Role |
|---------|-----------|------|------|
| `caddy` | Custom (caddy:2-alpine + cloudflare DNS module) | 80, 443 | TLS termination, reverse proxy to frontend |
| `frontend` | `nginx:1.27-alpine` | internal | Serves React SPA, reverse-proxies API to backend |
| `backend` | `python:3.11-slim` | internal | FastAPI + uvicorn with 2 workers |

Key files:
- `Dockerfile.frontend`: Multi-stage build (node:20-alpine → nginx:1.27-alpine), non-root user
- `Dockerfile.backend`: python:3.11-slim, non-root user, tini init
- `Dockerfile.caddy`: Custom Caddy build with cloudflare DNS module via xcaddy
- `docker/Caddyfile`: Caddy config (TLS via Cloudflare DNS, reverse proxy, security headers)
- `docker/default.conf`: nginx reverse proxy config (mirrors Vite dev proxy from `vite.config.ts`)
- `docker/nginx.conf`: Main nginx config (gzip, rate limiting for API and login)

## CI/CD

### `.github/workflows/ci.yml` — PR Checks
Triggers on `pull_request` to `main`. Jobs: `frontend-checks` (lint, typecheck, build), `backend-checks` (ruff, pytest), `docker-build` (build all 3 images, no push).

### `.github/workflows/deploy.yml` — Main Branch Deployment
Triggers on `push` to `main`. Jobs: `security` → `test` → `build-images` (push to GHCR + Trivy scan for frontend/backend/caddy) → `deploy` (SSH) → `cleanup`.

Required GitHub Secrets: `PROD_HOST`, `PROD_USER`, `PROD_SSH_KEY`, `SLACK_WEBHOOK_URL` (optional), `TURNSTILE_SITE_KEY` (optional, for CAPTCHA). `GITHUB_TOKEN` is automatic.

## Configuration

Create a `.env` file in the project root:

```bash
# ============================================
# AI Provider Configuration
# ============================================
LLM_PROVIDER=gemini

# --- Gemini Configuration (Google) ---
GOOGLE_API_KEY=AIzaSy...
GEMINI_MODEL=gemini-3.1-pro-preview
# Alternative: gemini-3-flash-preview

# --- OpenAI Configuration ---
# OPENAI_API_KEY=sk-...
# OPENAI_MODEL=gpt-5.3

# --- Anthropic Claude Configuration ---
# ANTHROPIC_API_KEY=sk-ant-...
# ANTHROPIC_MODEL=claude-opus-4-6-20250205

# --- Z.AI GLM Configuration ---
# ZAI_API_KEY=...
# ZAI_MODEL=glm-5.1

# ============================================
# AWS Configuration
# ============================================
AWS_ACCOUNT_ID=123456789012
AWS_ROLE_NAME=AgentPOCSessionRole

# ============================================
# Authentication (optional — omit for no-auth local dev)
# ============================================
# AUTH_USERNAME=admin
# AUTH_PASSWORD_HASH=$2b$12$...   # Generate with: python backend/scripts/hash_password.py
# JWT_SECRET=your-random-secret-32-chars-minimum
# JWT_EXPIRY_HOURS=8
# TURNSTILE_SECRET_KEY=0x...      # Cloudflare Turnstile server key

# ============================================
# Caddy / HTTPS (production only)
# ============================================
# CLOUDFLARE_API_TOKEN=...        # Cloudflare token with Zone:DNS:Edit
# CADDY_DOMAIN=iam.yantorno.dev
# ACME_EMAIL=admin@yantorno.dev

# ============================================
# Optional Configuration
# ============================================
SLACK_WEBHOOK_URL=https://hooks.slack.com/...
APPROVER_NAME=Admin
```

**Authentication behavior:** When `AUTH_PASSWORD_HASH` is empty/unset, authentication is completely disabled — all endpoints are open and the login page is not shown. This preserves the local dev workflow.

## Security Guardrails

The LLM system instruction enforces:
1. **No wildcards** (`*:*`) on sensitive actions/resources (scored as HIGH/CRITICAL)
2. **Specific resource ARNs** when user mentions specific buckets/resources
3. **Strict JSON schema** for policy response
4. **Least privilege** interpretation of vague requests

Risk-based duration limits:
- Low: 12 hours max
- Medium: 4 hours max
- High: 2 hours max
- Critical: 1 hour max

## Frontend Views

### Login View (`frontend/src/views/login-view.tsx`)
- Username/password form with optional Cloudflare Turnstile CAPTCHA
- Only shown when auth is required (`AUTH_PASSWORD_HASH` is set)
- Stores JWT in localStorage, uses AuthProvider context

### Request View (`frontend/src/views/request-view.tsx`)
- Natural language input for access request
- Duration slider (1-12 hours)
- LLM provider selector
- Template buttons for common patterns

### Review View (`frontend/src/views/review-view.tsx`)
- Display generated policy (JSON)
- Risk assessment badge
- Approver note and explanation
- Issue credentials or reject buttons

### Credentials View (`frontend/src/views/credentials-view.tsx`)
- Display temporary credentials
- Multiple export formats (Bash, PowerShell, AWS CLI)
- Expiration time
- New request button

### Rejected View (`frontend/src/views/rejected-view.tsx`)
- Rejection reason
- AI-generated guidance for resubmission
- Markdown-formatted suggestions
- Revise request or start fresh buttons

## API Endpoints

**Public (no auth required):**
- `GET /health` - Health check
- `GET /` - Root endpoint
- `POST /api/auth/login` - Authenticate and get JWT token
- `GET /api/auth/verify` - Check if current session is valid

**Protected (requires JWT when auth is enabled):**
- `GET /config/providers` - Get available LLM providers
- `POST /api/generate-policy` - Generate IAM policy from natural language
- `POST /api/issue-credentials` - Issue temporary AWS credentials
- `POST /api/generate-rejection-guidance` - Get AI guidance for rejected requests

## Roadmap (See GEMINI.md)

Phase 2: Model Context Protocol (MCP) integration for resource validation tools
Phase 3: Advanced approval workflows (Slack interactive buttons, Jira integration)
