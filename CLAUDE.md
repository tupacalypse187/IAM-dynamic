# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**IAM-Dynamic** is an AI-driven Just-In-Time AWS IAM access request portal. It uses Google Gemini 3.0 (with OpenAI fallback) to generate least-privilege IAM policies from natural language requests, then issues temporary credentials via AWS STS.

## Architecture

### Dual-Engine Strategy Pattern

The application uses a Strategy Pattern ([`llm_service.py`](llm_service.py)) to support multiple AI providers:

- **`LLMProvider`** (ABC): Abstract base class defining `generate_policy(request_text: str) -> PolicyResponse`
- **`GeminiProvider`**: Default engine using `google.generativeai` with Gemini 3.0 Pro/Flash
- **`OpenAIProvider`**: Legacy fallback using OpenAI's API

The provider is selected via `LLM_PROVIDER` environment variable (`gemini` or `openai`).

### Application Entry Points

1. **`dynamicIAM_web.py`**: Main Streamlit application (current)
   - Direct STS AssumeRole calls (no Lambda middleware)
   - Modern dashboard UI with session history, quick templates, agentic status visualization
   - Three-stage workflow: request → review → credentials

2. **`dynamicIAM_lambda.py`**: Legacy Streamlit UI
   - Calls backend Lambda function for credential issuance
   - Single-stage form, simpler UI
   - Kept for backward compatibility

3. **`lambda_credential_issuer.py`**: AWS Lambda backend (legacy)
   - Used only by `dynamicIAM_lambda.py`
   - Performs STS AssumeRole with session policy
   - Returns credentials with metadata

### Data Flow

```
User Request → LLMProvider.generate_policy() → PolicyResponse
                                                        ↓
                              {policy, risk, explanation, approver_note}
                                                        ↓
                            Risk-based auto-approval OR manual approval
                                                        ↓
                                    boto3 sts.assume_role() → Credentials
                                                        ↓
                                          Display + Slack audit log
```

### Session State Management

Streamlit session state tracks the workflow through stages (`request` → `review` → `completed`). Key keys:
- `stage`: Current workflow stage
- `policy_response`: `PolicyResponse` object from LLM
- `creds`: Temporary AWS credentials
- `history`: List of past requests (displayed in sidebar)
- `auto_approved` / `needs_approval`: Boolean flags

## Running the Application

```bash
# Setup
python3 -m venv venv
source venv/bin/activate  # venv\bin\activate on Windows
pip install -r requirements.txt

# Run (default binds to localhost:8501)
streamlit run dynamicIAM_web.py

# Run with custom address
streamlit run dynamicIAM_web.py --server.address 0.0.0.0
```

## Configuration

Create a `.env` file in the project root:

```bash
# AI Provider (required)
LLM_PROVIDER=gemini
GOOGLE_API_KEY=AIzaSy...
GEMINI_MODEL=gemini-3.0-pro  # or gemini-3.0-flash

# Fallback / Legacy
# OPENAI_API_KEY=sk-...

# AWS (required)
AWS_ACCOUNT_ID=123456789012
AWS_ROLE_NAME=AgentPOCSessionRole  # Role ARN: arn:aws:iam::{ACCOUNT_ID}:role/{ROLE_NAME}

# Optional
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
- Low: 8 hours max
- Medium: 4 hours max
- High: 2 hours max
- Critical: 1 hour max

## UI Components

### Quick Templates
Located in `dynamicIAM_web.py:137-145`, these one-click prompts pre-fill common access patterns:
- S3 Read-Only
- EC2 Observer
- Lambda Invoker

### Credential Display Formats
Credentials are displayed in three formats via tabs:
- Bash/Zsh (`export` variables)
- PowerShell (`$Env:` variables)
- AWS CLI Profile (`aws configure set`)

## Roadmap (See GEMINI.md)

Phase 2: Model Context Protocol (MCP) integration for resource validation tools
Phase 3: Advanced approval workflows (Slack interactive buttons, Jira integration)
