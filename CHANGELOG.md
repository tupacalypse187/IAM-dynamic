# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

## [3.0.0] - 2025-01-30

### 🚀 Major Architecture Migration

This release represents a complete architectural overhaul, migrating from a monolithic Streamlit application to a modern React/FastAPI architecture.

### Breaking Changes

- **Streamlit Application Removed**: The legacy Streamlit UI (`dynamicIAM_web.py`, `dynamicIAM_lambda.py`) has been decommissioned
- **New Frontend URL**: http://localhost:3000 (React SPA)
- **New Backend API**: http://localhost:8000 (FastAPI with `/docs` for OpenAPI documentation)
- **Environment Configuration**: Restructured for multi-provider LLM support

### New Features

- **Multi-Provider LLM Support**:
  - Google Gemini 3 Pro Preview (default)
  - OpenAI GPT-5.1
  - Anthropic Claude Opus 4.5
  - Zhipu GLM-4.7
  - Runtime provider switching via UI

- **Modern React Frontend**:
  - TypeScript with Vite for fast development
  - Multi-view state machine (request → review → credentials/rejected)
  - System theme detection (light/dark/system)
  - Responsive design with Tailwind CSS
  - Radix UI components for accessibility

- **Enhanced User Experience**:
  - Rejection flow with AI-generated guidance for resubmission
  - Markdown-formatted AI guidance with syntax highlighting
  - Multiple credential export formats (Bash, PowerShell, AWS CLI)
  - Real-time policy risk assessment with color-coded badges

### Technical Improvements

- **Backend**:
  - FastAPI REST API with automatic OpenAPI documentation
  - Comprehensive error handling and logging
  - CORS configuration for frontend-backend communication
  - Health check endpoint for monitoring

- **Security**:
  - Risk-based duration limits (Low: 12h, Medium: 4h, High: 2h, Critical: 1h)
  - Slack webhook notifications for audit trail
  - AWS STS AssumeRole with session policies

### Migration Guide

For users upgrading from v2.x:

1. Install new dependencies:
   ```bash
   pip install -r backend/requirements.txt
   cd frontend && npm install
   ```

2. Update `.env` configuration (see `.env.example`)

3. Start the new architecture:
   ```bash
   ./start-dev.sh
   # Or separately:
   cd backend && python main.py
   cd frontend && npm run dev
   ```

### Removed Features

- Streamlit-based UI (use new React frontend at localhost:3000)
- Lambda middleware (backend now calls STS directly)
- Legacy database service (not used in new architecture)

## [2.0.0] - 2025-12-21

### 🚀 Major Features
- **Gemini 3.0 Integration:** Switched default LLM engine to Google Gemini 3.0 Pro.
- **Dual-Engine Architecture:** Introduced `llm_service.py` to support both Gemini and OpenAI (legacy) via configuration.
- **UI Overhaul:** Completely redesigned `dynamicIAM_web.py` with a modern dashboard layout, sidebar history, and quick-action templates.

### 💅 User Experience
- **Agentic Feedback:** Added `st.status` containers to visualize the AI's reasoning steps.
- **Session History:** Users can now see a log of their recent requests and retrieve credentials from the sidebar.
- **Visual Risk Scoring:** Risk scores are now displayed as prominent metrics with color-coded badges.

### ⚙️ Configuration
- Added `LLM_PROVIDER`, `GOOGLE_API_KEY`, and `GEMINI_MODEL` to environment variables.
- Added `google-generativeai` to `requirements.txt`.

### 🛡️ Security
- Enhanced System Instructions for Gemini to strictly enforce JSON output and penalize wildcard permissions.
