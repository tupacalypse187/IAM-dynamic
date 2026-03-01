# IAM-Dynamic - Modern React/TypeScript + FastAPI Architecture

AI-driven Just-In-Time AWS IAM access request portal with a modern, polished UI.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│           React/TypeScript Frontend                │
│  (Vite + React + TypeScript + Tailwind + shadcn/ui)│
│              Serves on :3000                        │
└─────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────┐
│           Python Backend (FastAPI)                  │
│  - LLM policy generation                           │
│  - AWS STS credential issuance                     │
│  - Slack notifications                             │
│              Serves on :8000                        │
└─────────────────────────────────────────────────────┘
```

## Features

- **Modern UI**: Built with React, TypeScript, and shadcn/ui components
- **Dark Mode**: Built-in theme switching
- **FastAPI Backend**: Type-safe Python API with automatic OpenAPI docs
- **Multiple LLM Providers**: Gemini, OpenAI, Claude, and Zhipu GLM
- **Risk-Based Approval**: Auto-approval for low-risk requests
- **Temporary Credentials**: AWS STS-based time-limited access

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+
- AWS Account with IAM role configured
- API keys for at least one LLM provider

### Installation

1. **Clone the repository**
   ```bash
   cd IAM-dynamic
   ```

2. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys and AWS configuration
   ```

3. **Install Backend Dependencies**
   ```bash
   cd backend
   pip install -r requirements.txt  # or: uv pip install -r requirements.txt
   ```

4. **Install Frontend Dependencies**
   ```bash
   cd ../frontend
   npm install
   ```

### Running the Application

**Terminal 1 - Backend:**
```bash
cd backend
python main.py
# or: uvicorn main:app --reload --port 8000
```

**Terminal 2 - Frontend:**
```bash
cd frontend
npm run dev
```

- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- Frontend: http://localhost:3000

## Environment Variables

```bash
# AI Provider (required)
LLM_PROVIDER=gemini
GOOGLE_API_KEY=your_api_key
GEMINI_MODEL=gemini-3-pro-preview

# AWS (required)
AWS_ACCOUNT_ID=123456789012
AWS_ROLE_NAME=AgentPOCSessionRole

# Optional
SLACK_WEBHOOK_URL=https://hooks.slack.com/...
APPROVER_NAME=Admin
```

## Supported LLM Providers

- **Google Gemini**: Gemini 3 Pro Preview (default)
- **OpenAI**: GPT-5.1, GPT-5, o3-pro
- **Anthropic Claude**: Opus 4.5, Sonnet 4.5
- **Zhipu GLM**: GLM-4.7

## Project Structure

```
IAM-dynamic/
├── backend/                 # FastAPI backend
│   ├── main.py             # FastAPI application
│   ├── services/           # Service modules
│   ├── llm_service.py      # LLM provider implementations
│   └── config.py           # Configuration management
├── frontend/               # React/TypeScript frontend
│   ├── src/
│   │   ├── components/    # UI components
│   │   ├── views/         # Page components
│   │   ├── lib/           # Utilities and API client
│   │   └── types/         # TypeScript types
│   ├── package.json
│   └── vite.config.ts
└── .env                   # Environment configuration
```

## Development

### Backend Development

```bash
cd backend
uvicorn main:app --reload --port 8000
```

### Frontend Development

```bash
cd frontend
npm run dev
```

### Building for Production

**Backend:**
```bash
cd backend
# Deploy with any ASGI server (Gunicorn, Uvicorn)
uvicorn main:app --host 0.0.0.0 --port 8000
```

**Frontend:**
```bash
cd frontend
npm run build
# Serve the dist/ directory with nginx or similar
```

## API Endpoints

- `GET /health` - Health check
- `GET /config/providers` - Get available LLM providers
- `POST /api/generate-policy` - Generate IAM policy from natural language
- `POST /api/issue-credentials` - Issue temporary AWS credentials

## Security

- All credential issuance is logged for audit
- Temporary credentials expire automatically
- Risk-based approval workflow
- No permanent credentials stored

## License

MIT
