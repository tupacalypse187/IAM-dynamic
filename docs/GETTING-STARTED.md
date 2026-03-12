# 🚀 Getting Started with IAM-Dynamic

Welcome! This guide will help you get **IAM-Dynamic** up and running in about 5 minutes.

---

## 📋 What You'll Need

| Requirement | Why | How to Get It |
|-------------|------|---------------|
| **Python 3.11+** | Backend runtime | [python.org](https://www.python.org/downloads/) or `brew install python3` |
| **Node.js 20+** | Frontend build | [nodejs.org](https://nodejs.org/) or `brew install node` |
| **Docker** (optional) | Container runtime | [docker.com](https://www.docker.com/products/docker-desktop/) |
| **AWS CLI** (optional) | AWS setup | [docs.aws.amazon.com/cli](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) |
| **AI Provider API Key** | Policy generation | See [Provider Setup](#-ai-provider-setup) below |

---

## ⚡ Quick Start (5 Minutes)

### Step 1: Clone and Enter Directory

```bash
git clone https://github.com/tupacalypse187/IAM-dynamic.git
cd IAM-dynamic
```

### Step 2: Run the Setup Script

```bash
./setup.sh
```

The setup script will:
- ✅ Check prerequisites
- ✅ Configure AWS (IAM role + user)
- ✅ Set up authentication (optional)
- ✅ Configure your AI provider
- ✅ Validate everything works

### Step 3: Start the Application

```bash
docker compose up --build
```

### Step 4: Open Your Browser

Navigate to **http://localhost:8080**

That's it! 🎉

---

## 🎥 Walkthrough

### What the Setup Script Does

```
┌─────────────────────────────────────────────────────────────┐
│  IAM-Dynamic Setup                                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. Check Prerequisites                                    │
│     ├── Python 3.11+                                       │
│     ├── Node.js 20+                                        │
│     ├── Docker (optional)                                  │
│     └── AWS CLI (if setting up AWS)                        │
│                                                             │
│  2. AWS Setup (via setup-aws.sh)                           │
│     ├── Create IAM role with trust policy                   │
│     ├── Create IAM user with credentials                    │
│     └── Update .env with AWS configuration                  │
│                                                             │
│  3. Auth & LLM Setup (via setup-auth.sh)                   │
│     ├── Configure admin password (optional)                │
│     ├── Generate JWT secret                                 │
│     ├── Select LLM provider (Gemini, OpenAI, etc.)         │
│     └── Enter API key                                      │
│                                                             │
│  4. Validate Configuration                                 │
│     ├── Check .env exists                                  │
│     ├── Verify required variables set                       │
│     └── Warn about optional variables                       │
│                                                             │
│  5. Start Application (optional)                           │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔑 AI Provider Setup

Choose one (or more) AI providers:

| Provider | Model Options | Get API Key | Docs |
|----------|---------------|-------------|------|
| **Google Gemini** | gemini-3-pro-preview, gemini-3-flash-preview, gemini-2.5-pro | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) | [models](https://ai.google.dev/api/models) |
| **OpenAI** | gpt-5.1, gpt-4o, o1-preview | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) | [models](https://platform.openai.com/docs/models) |
| **Anthropic Claude** | claude-opus-4-6, claude-opus-4-5, claude-sonnet-4-5 | [console.anthropic.com/settings/keys](https://console.anthropic.com/settings/keys) | [models](https://docs.anthropic.com/en/docs/models-overview) |
| **Z.AI GLM (Global)** | glm-5, glm-4.7, glm-4.7-flash | [api.z.ai](https://api.z.ai) | [docs](https://docs.z.ai/guides/llm/glm-5) |

> **Tip:** The setup script can fetch available models when you provide your API key. Model availability depends on your provider account and region.

### Setup During Script

When the setup script asks for your provider:

```
Available LLM providers:
  1) gemini     — Google Gemini (default)
  2) openai     — OpenAI GPT
  3) anthropic  — Anthropic Claude
  4) zhipu      — Zhipu GLM

Provider [gemini]:
```

Type your choice (or press Enter for Gemini), then paste your API key when prompted.

---

## 🛠️ Setup Modes

### Interactive Mode (Default)

```bash
./setup.sh
```

Prompts you through each step with sensible defaults.

### Quick Mode

```bash
./setup.sh --quick
```

Uses defaults for most options. Fewer prompts.

### CI/CD Mode

```bash
./setup.sh --ci
```

Fully automated. No prompts. Great for scripts or testing.

### Skip Specific Steps

```bash
./setup.sh --skip-aws    # Skip AWS setup
./setup.sh --skip-auth   # Skip auth setup
```

Useful if you've already configured part of the system.

---

## 📁 Your `.env` File

After setup, your `.env` file will contain:

```bash
# AI Provider
LLM_PROVIDER=gemini
GOOGLE_API_KEY=AIzaSy...
GEMINI_MODEL=gemini-3.1-pro-preview

# AWS Configuration
AWS_ACCOUNT_ID=123456789012
AWS_ROLE_NAME=AgentPOCSessionRole
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
AWS_DEFAULT_REGION=us-east-1

# Authentication (optional)
AUTH_USERNAME=admin
AUTH_PASSWORD_HASH=$2b$12$...
JWT_SECRET=...
JWT_EXPIRY_HOURS=8

# Optional
APPROVER_NAME=Admin
SLACK_WEBHOOK_URL=https://hooks.slack.com/...
```

> **⚠️ Security Note:** Never commit `.env` to version control!

---

## 🏃 Running the Application

### Option 1: Docker (Recommended)

```bash
docker compose up --build
```

Access at **http://localhost:8080**

### Option 2: Development Mode

```bash
./start-dev.sh
```

Access at **http://localhost:3000** (frontend) and **http://localhost:8000** (API docs)

### Option 3: Manual

```bash
# Terminal 1: Backend
cd backend
python main.py

# Terminal 2: Frontend
cd frontend
npm install
npm run dev
```

---

## ✅ Making Your First Request

1. **Open** the application in your browser
2. **Enter** a natural language request:
   ```
   I need read-only access to the S3 bucket named my-data-bucket
   ```
3. **Select** a duration (1-12 hours)
4. **Click** "Generate Policy"
5. **Review** the generated IAM policy and risk assessment
6. **Approve** to receive temporary credentials

---

## 🐛 Troubleshooting

### Port Already in Use

```
Error: bind: address already in use
```

**Find and stop the conflicting process:**

```bash
# macOS/Linux
lsof -i :8080
lsof -i :8000

# Windows PowerShell
netstat -ano | findstr :8080
```

### AWS Credentials Not Working

```
✗ Failed to issue credentials
```

**Verify your AWS credentials:**

```bash
aws sts get-caller-identity
```

Make sure the IAM role exists and your user is in the trust policy.

### AI Provider Errors

```
✗ Failed to generate policy
```

**Check your API key:**

- Verify the key is correct
- Check you have available quota/tokens
- Ensure network connectivity to the API

---

## 📚 Next Steps

| Goal | Guide |
|------|-------|
| **Configure AWS manually** | [AWS Setup Guide](./AWS-SETUP.md) |
| **Deploy to production** | [VPS Deployment Guide](./vps-setup-guide.md) |
| **Run locally with Docker** | [Local Docker Testing](./local-docker-testing.md) |
| **Deploy on home lab** | [Antsle Deployment Guide](./antsle-deployment-guide.md) |
| **Kubernetes deployment** | [MicroK8s ArgoCD Guide](./microk8s-argocd-deployment-guide.md) |

---

## 🆘 Getting Help

- 📖 **Documentation**: Check the `docs/` folder
- 🐛 **Issues**: [GitHub Issues](https://github.com/tupacalypse187/IAM-dynamic/issues)
- 💬 **Discussions**: [GitHub Discussions](https://github.com/tupacalypse187/IAM-dynamic/discussions)

---

## 🎓 Concepts

### How It Works

```
┌──────────────┐     Natural Language      ┌──────────────┐
│   User       │ ────────────────────────> │ IAM-Dynamic  │
│              │                           │              │
└──────────────┘                           └──────┬───────┘
                                                  │
                                                  ▼
┌─────────────────────────────────────────────────────────────┐
│                     AI Policy Generation                    │
│  • Analyzes request using LLM (Gemini, GPT, Claude, GLM)    │
│  • Generates least-privilege IAM policy                     │
│  • Assesses risk (Low, Medium, High, Critical)              │
│  • Auto-approves low-risk requests                          │
└─────────────────────────────────────────────────────────────┘
                                                  │
                                                  ▼
┌─────────────────────────────────────────────────────────────┐
│                  AWS STS AssumeRole                         │
│  • Issues temporary credentials                             │
│  • Scoped by session policy                                 │
│  • Expires after requested duration                         │
└─────────────────────────────────────────────────────────────┘
```

### Security Architecture

| Layer | Description |
|-------|-------------|
| **AI Guardrails** | System instructions prevent over-privileged policies |
| **Risk Assessment** | Duration limits based on risk level |
| **Session Policies** | Credentials scoped to generated policy only |
| **Temporary Access** | Credentials auto-expire (max 12 hours) |
| **Audit Trail** | Optional Slack logging for all requests |

---

**Happy credential issuing! 🎉**
