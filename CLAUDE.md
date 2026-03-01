# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**IAM-Dynamic** is an AI-driven Just-In-Time AWS IAM access request portal. It uses multiple LLM providers (Google Gemini, OpenAI, Anthropic Claude, Zhipu GLM) to generate least-privilege IAM policies from natural language requests, then issues temporary credentials via AWS STS.

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
  - Multi-provider LLM support (Gemini, OpenAI, Anthropic, Zhipu)
  - Policy generation and validation endpoints
  - Credential issuance via AWS STS AssumeRole
  - Rejection guidance with AI-powered suggestions
  - Comprehensive error handling and logging
  - OpenAPI documentation at `/docs`

### LLM Service Layer

The backend uses a Strategy Pattern ([`backend/llm_service.py`](backend/llm_service.py)) to support multiple AI providers:

- **`LLMProvider`** (ABC): Abstract base class defining `generate_policy(request_text: str) -> PolicyResponse`
- **`GeminiProvider`**: Default engine using `google.genai` with Gemini 3 Pro Preview
- **`OpenAIProvider`**: OpenAI GPT-5.1
- **`AnthropicProvider`**: Anthropic Claude Opus 4.5
- **`ZhipuProvider`**: Zhipu GLM-4.7

The provider is selected via `LLM_PROVIDER` environment variable (`gemini`, `openai`, `claude`, or `glm`).

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
   - Views: request, review, credentials, rejected

2. **Backend**: `backend/main.py`
   - FastAPI application with API endpoints
   - Health check, provider config, policy generation, credential issuance, rejection guidance

### Backend Services

- **`backend/services/sts_service.py`**: AWS STS AssumeRole with session policies
- **`backend/services/slack_service.py`**: Webhook notifications for audit trail

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

Two-container setup orchestrated by docker-compose:

| Service | Base Image | Port | Role |
|---------|-----------|------|------|
| `frontend` | `nginx:1.27-alpine` | 8080 | Serves React SPA, reverse-proxies `/api`, `/health`, `/config`, `/docs` to backend |
| `backend` | `python:3.11-slim` | 8000 | FastAPI + uvicorn with 2 workers |

Key files:
- `Dockerfile.frontend`: Multi-stage build (node:20-alpine → nginx:1.27-alpine), non-root user
- `Dockerfile.backend`: python:3.11-slim, non-root user, tini init
- `docker/default.conf`: nginx reverse proxy config (mirrors Vite dev proxy from `vite.config.ts`)
- `docker/nginx.conf`: Main nginx config (gzip, rate limiting)

## CI/CD

### `.github/workflows/ci.yml` — PR Checks
Triggers on `pull_request` to `main`. Jobs: `frontend-checks` (lint, typecheck, build), `backend-checks` (ruff, pytest), `docker-build` (build both images, no push).

### `.github/workflows/deploy.yml` — Main Branch Deployment
Triggers on `push` to `main`. Jobs: `security` → `test` → `build-images` (push to GHCR + Trivy scan) → `deploy` (SSH) → `cleanup`.

Required GitHub Secrets: `PROD_HOST`, `PROD_USER`, `PROD_SSH_KEY`, `SLACK_WEBHOOK_URL` (optional). `GITHUB_TOKEN` is automatic.

## Configuration

Create a `.env` file in the project root:

```bash
# ============================================
# AI Provider Configuration
# ============================================
LLM_PROVIDER=gemini

# --- Gemini Configuration (Google) ---
GOOGLE_API_KEY=AIzaSy...
GEMINI_MODEL=gemini-3-pro-preview
# Alternative: gemini-3-flash-preview

# --- OpenAI Configuration ---
# OPENAI_API_KEY=sk-...
# OPENAI_MODEL=gpt-5.1

# --- Anthropic Claude Configuration ---
# ANTHROPIC_API_KEY=sk-ant-...
# ANTHROPIC_MODEL=claude-opus-4-5-20251101

# --- Zhipu GLM Configuration ---
# ZHIPUAI_API_KEY=...
# ZHIPUAI_MODEL=glm-4.7

# ============================================
# AWS Configuration
# ============================================
AWS_ACCOUNT_ID=123456789012
AWS_ROLE_NAME=AgentPOCSessionRole

# ============================================
# Optional Configuration
# ============================================
SLACK_WEBHOOK_URL=https://hooks.slack.com/...
APPROVER_NAME=Admin
```

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

- `GET /health` - Health check
- `GET /config/providers` - Get available LLM providers
- `POST /api/generate-policy` - Generate IAM policy from natural language
- `POST /api/issue-credentials` - Issue temporary AWS credentials
- `POST /api/generate-rejection-guidance` - Get AI guidance for rejected requests

## Roadmap (See GEMINI.md)

Phase 2: Model Context Protocol (MCP) integration for resource validation tools
Phase 3: Advanced approval workflows (Slack interactive buttons, Jira integration)
