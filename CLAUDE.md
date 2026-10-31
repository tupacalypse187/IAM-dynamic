# 🤖 CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 📑 Table of Contents

- [📋 Project Overview](#-project-overview)
- [🏗️ Architecture](#-architecture)
- [🚀 Running the Application](#-running-the-application)
- [🐳 Docker Architecture](#-docker-architecture)
- [🔄 CI/CD](#-cicd)
- [⚙️ Configuration](#-configuration)
- [🛡️ Security Guardrails](#-security-guardrails)
- [🖥️ Frontend Views](#-frontend-views)
- [🖥️ Desktop App (Electron)](#-desktop-app-electron)
- [🔌 API Endpoints](#-api-endpoints)
- [📚 Zread Wiki (`.zread/`)](#-zread-wiki-zread)
- [🗺️ Roadmap (See GEMINI.md)](#-roadmap-see-geminimd)

## 📋 Project Overview

**IAM-Dynamic** is an AI-driven Just-In-Time AWS IAM access request portal. It uses multiple LLM providers (Google Gemini, OpenAI, Anthropic Claude, Z.AI GLM, Meta Muse, OpenRouter) to generate least-privilege IAM policies from natural language requests, then issues temporary credentials via AWS STS.

## 🏗️ Architecture

### Modern React/FastAPI Architecture (v3.0+)

The application uses a modern frontend/backend separation pattern:

- **Frontend (`frontend/`)**: React SPA with TypeScript, Vite, and Tailwind CSS
  - Views: submit → my requests → detail → credentials/denied, plus an admin-only review dashboard
  - Draggable title bar (app name, version, user) separated from the clickable toolbar
  - System theme detection and toggle (light/dark/system)
  - LLM provider/model selector with real-time switching
  - Markdown-formatted AI guidance with syntax highlighting
  - Multiple credential export formats (Bash, PowerShell, AWS CLI)

- **Backend (`backend/`)**: FastAPI REST API
  - Multi-provider LLM support (Gemini, OpenAI, Anthropic, Z.AI, Muse, OpenRouter)
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
- **`GeminiProvider`**: Default engine using `google.genai` with Gemini 4 Argon
- **`OpenAICompatibleProvider`**: Shared base for OpenAI-compatible Chat Completions APIs — subclasses declare env vars, base URL, default model, and parameter capabilities (`supports_json_response_format`, `supports_temperature`)
  - **`OpenAIProvider`**: OpenAI GPT-6 family
  - **`ZhipuProvider`**: Z.AI GLM-5.3 (global platform via api.z.ai coding endpoint)
  - **`MuseProvider`**: Meta Muse Spark 1.3 (Meta Model API via api.meta.ai)
  - **`OpenRouterProvider`**: OpenRouter gateway using `vendor/model` slugs (e.g. `z-ai/glm-5.3`)
- **`AnthropicProvider`**: Anthropic Claude Opus 5.5

The provider is selected via `LLM_PROVIDER` environment variable (`gemini`, `openai`, `anthropic`/`claude`, `zhipu`/`glm`, `muse`/`meta`, or `openrouter`) and can be switched per-request from the UI. The model catalog served to the frontend lives in `PROVIDER_MODELS` in `backend/main.py`.

Task-based model tiers: policy generation always uses the user-selected (frontier) model, while rejection guidance defaults to a fast/cheap tier (`FAST_MODELS` in `backend/main.py`, resolved via `fast_model_for()` with provider-alias handling) unless the caller pins an explicit model.

### Data Flow

```
User Request (React UI)
        ↓
FastAPI POST /api/requests  (LLM evaluate → persist → route)
        ↓
Low risk → approved (system)  |  else → pending_review
        ↓
Admin POST /api/requests/{id}/review (approve/deny/changes_requested)
        ↓
Owner POST /api/requests/{id}/activate  (approval alone issues nothing)
        ↓
boto3 sts.assume_role() → Credentials
        ↓
Display + Slack/Telegram audit log + JSONL audit trail
```

Request rows live in `backend/requests.db` (`services/request_store.py`);
every transition is appended to `backend/data/audit.jsonl`
(`services/audit_log.py`, metadata only — never credentials).
Legacy `POST /api/generate-policy` + `POST /api/issue-credentials` remain as
thin shims. Desktop submits persist via `POST /api/requests/record`
(same guardrails, no second LLM call).

### Application Entry Points

1. **Frontend**: `frontend/src/App.tsx`
   - Main React application with view routing
   - Auth gate: shows LoginView when auth is required and user is not authenticated
   - Views: login, submit, my requests, detail, review dashboard (admin-only), credentials, rejected, help
2. **Desktop**: `desktop/src/main/main.ts`
   - Electron entry: window, IPC, tray lease manager, global capture shortcut, auto-updater
   - Loads Vite dev server in dev, `frontend-dist/` in packaged builds

2. **Backend**: `backend/main.py`
   - FastAPI application with API endpoints
   - Health check, auth (login/verify with `is_admin`), provider config, access requests + review workflow, policy generation (legacy shim), credential issuance/activation, rejection guidance, audit trail (admin)
   - `get_current_user` dependency protects all endpoints except health and auth

### Desktop Shell (`desktop/`)

Electron app reusing the React frontend and the remote FastAPI backend (no Python bundling). Source of truth for IPC is [`desktop/src/shared/ipc-contract.ts`](desktop/src/shared/ipc-contract.ts); the renderer mirror lives in `frontend/src/types/desktop.ts`.

- **`desktop/src/main/main.ts`** — window (macOS `hiddenInset` + vibrancy), typed IPC handlers, tray, `Cmd/Ctrl+Shift+I` global capture, single-instance
- **`desktop/src/main/agentkit/`** — **Agent_Kit**: `router.ts` (intent extraction + ≤3 clarifying questions), `backend-client.ts` (remote API, incl. request activation), `audit-risk.ts` (deterministic guardrail — raises, never lowers, backend risk), `index.ts` (Router → Architect → Audit → Lifecycle orchestrator with progress events, plus `activateRequest` for approved-request issuance with lease/tray/ledger updates)
- **`desktop/src/main/ledger.ts`** — SQLite audit ledger (`better-sqlite3`, WAL, versioned migrations, Markdown/JSON export)
- **`desktop/src/main/vault.ts`** — OS credential store via lazy `keytar` (JWT only; temp AWS creds stay memory-only)
- **`desktop/src/main/updater.ts`** — `electron-updater` (generic provider): background download, install on user restart only
- **`desktop/src/main/tray-manager.ts`** — lease countdown title, 5-minute warning, revoke-on-expiry
- **`desktop/src/preload/preload.ts`** — `contextBridge` allowlist; the only renderer↔main surface
- **Packaging** — `electron-builder.yml` (arm64 dmg / x64 NSIS / arm64 AppImage+deb), `build/icon.py` (generates icons), `buildspec-windows.yml` + `scripts/setup-codebuild.sh` (on-demand Windows builds), `scripts/notarize.js` (skips without Apple creds)

Guides: [`docs/desktop-app.md`](docs/desktop-app.md), [`docs/auto-update.md`](docs/auto-update.md), [`desktop/README.md`](desktop/README.md)

### Backend Services

- **`backend/services/sts_service.py`**: AWS STS AssumeRole with session policies
- **`backend/services/slack_service.py`**: Slack Block Kit webhook notifications for audit trail
- **`backend/services/telegram_service.py`**: Telegram Bot API notifications (HTML messages, @BotFather credentials)
- **`backend/services/auth_service.py`**: JWT creation/verification, bcrypt password checking
- **`backend/services/user_store.py`**: SQLite user accounts (first registered user is admin); `POST /api/auth/register`, `GET /api/auth/users` (admin-only). Legacy `AUTH_USERNAME`/`AUTH_PASSWORD_HASH` login still works alongside. Disable open registration with `AUTH_ALLOW_REGISTRATION=false`
- **`backend/services/request_store.py`**: SQLite access requests with the review status machine (`pending_review → approved | denied | changes_requested | discarded`, `changes_requested → pending_review`, `approved → activated | discarded`); `AUTH_REQUESTS_DB` path, gitignored
- **`backend/services/audit_log.py`**: Append-only JSONL trail (`AUDIT_LOG_PATH`, default `backend/data/audit.jsonl`, gitignored) — metadata only, never credentials; actor roles `user` / `admin` / `automated`
- **`backend/services/turnstile_service.py`**: Cloudflare Turnstile CAPTCHA verification
- **`backend/services/error_handler.py`**: Maps provider API errors to actionable user-facing messages
- **`backend/tests/`**: pytest suite (config validation, provider factory, catalog integrity, API endpoints) — run with `pytest` from `backend/`

## 🚀 Running the Application

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

**Desktop shell (third terminal, after backend + frontend are up):**
```bash
cd desktop && npm install && npm run dev
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

## 🐳 Docker Architecture

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

## 🔄 CI/CD

### `.github/workflows/ci.yml` — PR Checks
Triggers on `pull_request` to `main`. Jobs: `frontend-checks` (lint, typecheck, build), `backend-checks` (ruff, pytest), `desktop-checks` (typecheck with `--ignore-scripts`), `docker-build` (build all 3 images, no push).

### `.github/workflows/deploy.yml` — Main Branch Deployment
Triggers on `push` to `main`. Jobs: `security` → `test` → `build-images` (push to GHCR + Trivy scan for frontend/backend/caddy) → `deploy` (SSH) → `cleanup`. A `publish-dockerhub` job mirrors all three images to Docker Hub when configured.

Required GitHub Secrets: `PROD_HOST`, `PROD_USER`, `PROD_SSH_KEY`, `SLACK_WEBHOOK_URL` (optional), `TURNSTILE_SITE_KEY` (optional, for CAPTCHA), `DOCKERHUB_USERNAME`/`DOCKERHUB_TOKEN` (optional — enables the Docker Hub publish job; it is skipped while unset). `GITHUB_TOKEN` is automatic for GHCR.

## ⚙️ Configuration

Create a `.env` file in the project root:

```bash
# ============================================
# AI Provider Configuration
# ============================================
LLM_PROVIDER=gemini

# --- Gemini Configuration (Google) ---
GOOGLE_API_KEY=AIzaSy...
GEMINI_MODEL=gemini-4-argon
# Alternative: gemini-3.8-flash

# --- OpenAI Configuration ---
# OPENAI_API_KEY=sk-...
# OPENAI_MODEL=gpt-6-astra

# --- Anthropic Claude Configuration ---
# ANTHROPIC_API_KEY=sk-ant-...
# ANTHROPIC_MODEL=claude-opus-5-5

# --- Z.AI GLM Configuration ---
# ZAI_API_KEY=...
# ZAI_MODEL=glm-5.3

# --- Meta Muse Configuration ---
# MUSE_API_KEY=...
# MUSE_MODEL=muse-spark-1.3-contributor

# --- OpenRouter Configuration (gateway) ---
# OPENROUTER_API_KEY=sk-or-...
# OPENROUTER_MODEL=z-ai/glm-5.3

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
# Telegram notifications (optional — both values required to enable)
# TELEGRAM_BOT_TOKEN=123456789:ABCdef...
# TELEGRAM_CHAT_ID=123456789
APPROVER_NAME=Admin
```

**Authentication behavior:** When `AUTH_PASSWORD_HASH` is empty/unset, authentication is completely disabled — all endpoints are open and the login page is not shown. This preserves the local dev workflow. With no legacy hash, in-app registration (`POST /api/auth/register`, first user becomes admin) activates auth from the login page; set `AUTH_ALLOW_REGISTRATION=false` for invite-only deployments.

**Desktop shell env vars** (shell environment, not `.env`): `IAM_DESKTOP_BACKEND_URL` (default `http://localhost:8000`), `IAM_DESKTOP_UPDATE_FEED_URL` (unset disables updates), `CSC_NAME` + `APPLE_ID`/`APPLE_APP_SPECIFIC_PASSWORD`/`APPLE_TEAM_ID` (signing + notarization).

## 🛡️ Security Guardrails

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

## 🖥️ Frontend Views

### Login View (`frontend/src/views/login-view.tsx`)
- Username/password form with optional Cloudflare Turnstile CAPTCHA, plus self-registration mode (first account becomes admin)
- Only shown when auth is required (`AUTH_PASSWORD_HASH` is set or users exist)
- Stores JWT in localStorage, uses AuthProvider context

### Request View (`frontend/src/views/request-view.tsx`)
- Task-first input ("what are you trying to do") + guided fields (task/resources/ticket) + free text
- Submits via `usePolicyAgent.submit`: desktop path evaluates through Agent_Kit (IPC with progress stages) then persists with `POST /api/requests/record`; browser path calls `POST /api/requests` directly
- Clarifying-question loop (≤3) when intent is underspecified; duration slider (1-12 hours)
- LLM provider selector; template buttons for common patterns

### My Requests View (`frontend/src/views/my-requests-view.tsx`)
- Live sessions (activated, unexpired), open requests, and the last 10 with Clone (resubmit as-is) / Clone & edit (prefill the submit form)

### Request Detail View (`frontend/src/views/request-detail-view.tsx`)
- Request text + evaluated LLM response (policy, risk, explanation, approver note), requester + reviewer identity, revision, timestamps
- Monaco read-only JSON editor (lazy-loaded chunk) with wildcard line highlighting + copy button; before/after diff tab on resubmits; plain-language grant summary (desktop path)
- Local guardrail findings with severity badges and one-click "Revise with this fix"
- Role-aware actions: owner activates approved requests (credentials only on activation) or withdraws open ones; admins approve/deny/send-back with mandatory feedback on deny/send-back; owners see denial feedback + guidance link

### Review Dashboard View (`frontend/src/views/review-dashboard-view.tsx`, admin-only)
- Queue with status filters (defaults to needs-review) + pending-count nav badge; rows show requester, risk, age
- Audit-trail tab (server JSONL, newest first) with links into request detail; per-request audit tab lives in the detail view

### Credentials View (`frontend/src/views/credentials-view.tsx`)
- Display temporary credentials
- Multiple export formats (Bash, PowerShell, AWS CLI) with copy buttons (clipboard API + legacy fallback)
- Live expiration countdown
- New request button

### Rejected View (`frontend/src/views/rejected-view.tsx`)
- Denial reason + reviewer name and feedback (from the review workflow)
- AI-generated guidance for resubmission
- GitHub-flavored markdown with syntax highlighting, styled tables, and per-code-block copy buttons
- Revise request or start fresh buttons

### Help View (`frontend/src/views/help-view.tsx`)
- Guided tour replay, how-to guides, keyboard shortcut reference (rendered from `lib/shortcuts.ts`)
- Update status + manual check, local audit log with Markdown/JSON export (desktop only)

### App Shell (`frontend/src/App.tsx`)
- Error boundary around view content (a render crash shows a recoverable fallback)
- Two-row header: draggable title bar (`.app-drag`, app name + version + user/role, macOS traffic-light safe area) above a clickable toolbar (`.app-no-drag`, view nav + pending-count badge + help + logout)
- Role-aware nav: New Request / My Requests for everyone, Review dashboard only for admins (`is_admin` from `/api/auth/verify`)
- Toast notifications (session expiry, copy failures) + `UpdateBanner` (desktop update downloaded/available)
- First-run guided tour (`lib/tour.ts`, driver.js, `data-tour` anchors), `?` shortcut → Help
- Desktop capture shortcut focuses the request box; vault-backed JWT via `desktop.setToken`
- Responsive layout: desktop sidebar rail + mobile navigation drawer

## 🖥️ Desktop App (Electron)

Full guides: [`docs/desktop-app.md`](docs/desktop-app.md) (run/build/sign/troubleshoot), [`docs/auto-update.md`](docs/auto-update.md) (feed, CodeBuild Windows releases), [`desktop/README.md`](desktop/README.md) (command reference).

- **Dev loop:** backend on :8000 → `frontend` dev server on :3000 → `desktop` (`npm run dev` loads the dev server; packaged builds use `frontend-dist/`)
- **Config:** `IAM_DESKTOP_BACKEND_URL` (default `http://localhost:8000`), `IAM_DESKTOP_UPDATE_FEED_URL` (unset = updates off), `CSC_NAME` + `APPLE_ID`/`APPLE_APP_SPECIFIC_PASSWORD`/`APPLE_TEAM_ID` for sign/notarize
- **Releases:** macOS arm64 `.dmg` locally; Windows x64 NSIS via on-demand CodeBuild (`desktop/scripts/setup-codebuild.sh` creates the project; builds start manually); Linux arm64 via Docker; publishing flags are CLI-only so local builds never phone home
- **Conventions:** IPC contract is the source of truth (`desktop/src/shared/` ↔ `frontend/src/types/desktop.ts` mirror); shortcuts live in `lib/shortcuts.ts` (Help renders them); tour anchors use `data-tour` attributes; Monaco must stay lazy-loaded (`components/policy-editor.tsx`)

## 🔌 API Endpoints

**Public (no auth required):**
- `GET /health` - Health check
- `GET /` - Root endpoint
- `POST /api/auth/login` - Authenticate and get JWT token
- `GET /api/auth/verify` - Check if current session is valid (includes `is_admin` for role gating)

**Protected (requires JWT when auth is enabled):**
- `GET /config/providers` - Get available LLM providers
- `POST /api/requests` - Evaluate + persist an access request (low risk → approved, else pending review)
- `POST /api/requests/record` - Persist a desktop-evaluated policy without re-running the LLM (same guardrails)
- `GET /api/requests` - List requests (own, or all for admins; `?status=` + `?mine=true`)
- `GET /api/requests/{id}` - Request detail with evaluated LLM response (owner or admin)
- `POST /api/requests/{id}/review` - Approve / deny / send back with feedback (admin only; feedback required for deny/send-back)
- `POST /api/requests/{id}/resubmit` - Re-evaluate a sent-back request as a new revision (owner only)
- `POST /api/requests/{id}/discard` - Withdraw an open request (owner or admin)
- `POST /api/requests/{id}/activate` - Issue STS credentials for an approved request when the owner is ready (re-checks the stored policy; approval alone issues nothing)
- `GET /api/audit` - Browse the JSONL audit trail (admin only; `?request_id=` / `?actor=` / `?event=`)
- `POST /api/generate-policy` - Legacy shim: stateless policy generation (no persistence)
- `POST /api/issue-credentials` - Legacy shim: direct issuance with caller-asserted approval
- `POST /api/generate-rejection-guidance` - Get AI guidance for rejected requests

## 📚 Zread Wiki (`.zread/`)

The `.zread/` directory contains a machine-generated wiki produced by [zread](https://zread.ai/cli). It breaks the codebase into topical markdown files (architecture, services, views, Docker, CI/CD, etc.) that can be used for quick orientation or fed to AI tools.

**Maintenance workflow:**
1. After meaningful code changes, run `zread generate` to refresh the wiki
2. Prune old version snapshots so only the latest remains: `rm -rf .zread/wiki/versions/<old-timestamp>/`
3. Commit the updated `.zread/` directory

**Gitignore:** `.zread/wiki/drafts/` is excluded (in-progress generation artifacts). Everything else (`current` pointer + latest `versions/` snapshot) is tracked.

## 🗺️ Roadmap (See GEMINI.md)

Phase 2: Model Context Protocol (MCP) integration for resource validation tools
Phase 3: Advanced approval workflows (Slack interactive buttons, Jira integration)
