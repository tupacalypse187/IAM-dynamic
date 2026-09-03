# ♊ Gemini Integration & Roadmap

This document outlines the strategic integration of Google's **Gemini** models into the **IAM-Dynamic** project.

## 🎯 Status: Implemented

✅ **Default Engine:** Gemini (`gemini-3.1-pro-preview`) is the default provider for policy generation.
✅ **Multi-Provider Architecture:** The `LLMProvider` interface allows swapping between Gemini, OpenAI, Anthropic Claude, Z.AI GLM, Meta Muse, and OpenRouter at runtime.
✅ **Modern UI:** A React SPA with TypeScript, Vite, and Tailwind CSS.
✅ **Guardrails:** The shared `SYSTEM_INSTRUCTION` enforces strict JSON schemas and least-privilege rules across all providers.

---

## 🛠️ Technical Implementation

### 1. Service Layer (`backend/llm_service.py`)

We use a Strategy Pattern to handle AI providers. OpenAI-compatible providers
(OpenAI, Z.AI GLM, Meta Muse, OpenRouter) share the `OpenAICompatibleProvider`
base class and only declare their env vars, base URL, default model, and
parameter capabilities:

```python
class GeminiProvider(LLMProvider):
    def __init__(self):
        # Configures google.genai with GOOGLE_API_KEY
        # Defaults to gemini-3.1-pro-preview
        ...

# Shared base for OpenAI-compatible APIs (used by 4 of the 6 providers)
class OpenAICompatibleProvider(LLMProvider):
    api_key_env = "OPENAI_API_KEY"
    model_env = "OPENAI_MODEL"
    default_model = "gpt-5.6"
    base_url = None  # None → OpenAI itself
    supports_json_response_format = True
    supports_temperature = True  # False for GPT-5 reasoning models
```

The system instruction (`SYSTEM_INSTRUCTION`) is a module-level constant that
enforces the JSON schema and "Least Privilege" rules for every provider.

### 2. User Experience (React Frontend)

The frontend provides a modern multi-view interface:

- **Request View**: Natural language input with templates and provider selection
- **Review View**: Policy display with risk assessment, JSON copy button, and a confirmation dialog on reject
- **Credentials View**: Temporary credentials with copyable Bash/PowerShell/AWS CLI export scripts
- **Rejected View**: AI-generated guidance rendered as GitHub-flavored markdown with syntax highlighting and per-code-block copy buttons

### 3. FastAPI Backend

- REST API with automatic OpenAPI documentation at `/docs`
- Health check endpoint at `/health`
- Multi-provider configuration endpoint at `/config/providers`
- Policy generation endpoint at `/api/generate-policy`
- Credential issuance endpoint at `/api/issue-credentials`
- Rejection guidance endpoint at `/api/generate-rejection-guidance`
- pytest suite in `backend/tests/` (config, factory, catalog, API endpoints)

---

## 🚀 Future Roadmap (Pending)

While the core integration is complete, the following "Agentic" features are planned:

### Phase 2: Model Context Protocol (MCP) Integration

To prevent "hallucinations" (e.g., policies for non-existent buckets), we will integrate Tool Use.

1. **Resource Validation Tool**:
   - *Goal:* The LLM calls `verify_s3_bucket(name)` before writing the policy.
   - *Behavior:* If the bucket is missing, the LLM asks the user for clarification instead of generating a broken policy.

2. **Identity Awareness**:
   - *Goal:* Pass the user's current identity context to the LLM to prevent self-escalation scenarios.

### Phase 3: Advanced Approval Workflows

- **Slack Interactive Buttons:** Allow approvers to click "Approve" directly in Slack.
- **Jira Integration:** Automatically create a ticket for "Critical" risk requests.

---

## 📝 Configuration

Configure Gemini in your `.env` file:

```bash
LLM_PROVIDER=gemini
GOOGLE_API_KEY=AIzaSy...
GEMINI_MODEL=gemini-3.1-pro-preview
```

Available models:

- `gemini-3.1-pro-preview` (default, flagship)
- `gemini-3.8-flash` (fast, stable)
- `gemini-3.7-flash` (fast, stable)
- `gemini-3.5-flash-lite` (lowest cost)

See [README.md](README.md) for the full multi-provider configuration reference.
