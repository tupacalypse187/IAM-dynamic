# ♊ Gemini Integration & Roadmap

This document outlines the strategic integration of Google's **Gemini 3** models into the **IAM-Dynamic** project.

## 🎯 Status: Implemented
✅ **Default Engine:** Gemini 3 Pro Preview is now the primary driver for policy generation.
✅ **Multi-Provider Architecture:** The `LLMProvider` interface allows swapping between Gemini, OpenAI, Anthropic Claude, and Zhipu GLM.
✅ **Modern UI:** A React SPA with TypeScript, Vite, and Tailwind CSS.
✅ **Guardrails:** System instructions now enforce strict JSON schemas and risk scoring.

---

## 🛠️ Technical Implementation

### 1. Service Layer (`backend/llm_service.py`)
We implemented a Strategy Pattern to handle AI providers.

```python
class GeminiProvider(LLMProvider):
    def __init__(self):
        # Configures google.genai with API Key
        # Defaults to gemini-3-pro-preview
        ...

    def _get_system_instruction(self) -> str:
        # Enforces JSON schema and "Least Privilege" rules
        ...
```

### 2. User Experience (React Frontend)
The frontend provides a modern multi-view interface:
- **Request View**: Natural language input with templates and provider selection
- **Review View**: Policy display with risk assessment and approval options
- **Credentials View**: Temporary credentials with multiple export formats
- **Rejected View**: AI-generated guidance for resubmission with markdown formatting

### 3. FastAPI Backend
- REST API with automatic OpenAPI documentation at `/docs`
- Health check endpoint at `/health`
- Multi-provider configuration endpoint at `/config/providers`
- Policy generation endpoint at `/api/generate-policy`
- Credential issuance endpoint at `/api/issue-credentials`
- Rejection guidance endpoint at `/api/generate-rejection-guidance`

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
GEMINI_MODEL=gemini-3-pro-preview
```

Available models:
- `gemini-3-pro-preview` (default, high quality)
- `gemini-3-flash-preview` (faster, lower cost)
