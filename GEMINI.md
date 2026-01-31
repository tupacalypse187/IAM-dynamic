# ♊ Gemini Integration & Roadmap

This document outlines the strategic integration of Google's **Gemini 3.0** models into the **IAM-Dynamic** project.

## 🎯 Status: Implemented
✅ **Default Engine:** Gemini 3.0 Pro is now the primary driver for policy generation.
✅ **Unified Architecture:** The `LLMProvider` interface allows swapping between Gemini and OpenAI.
✅ **UI Overhaul:** A modern "Agentic" dashboard has replaced the basic form.
✅ **Guardrails:** System instructions now enforce strict JSON schemas and risk scoring.

---

## 🛠️ Technical Implementation

### 1. Service Layer (`llm_service.py`)
We implemented a Strategy Pattern to handle AI providers.

```python
class GeminiProvider(LLMProvider):
    def __init__(self):
        # Configures google.generativeai with API Key
        # Defaults to gemini-3.0-pro
        ...
    
    def _get_system_instruction(self) -> str:
        # Enforces JSON schema and "Least Privilege" rules
        ...
```

### 2. User Experience (`dynamicIAM_web.py`)
The frontend was rebuilt to visualize the agent's thinking process:
-   **`st.status`**: Shows "Thinking...", "Validating...", "Drafting...".
-   **Session History**: Keeps track of previous credentials in the sidebar.
-   **Visual Metrics**: Risk scores and policy size are displayed as key metrics.

---

## 🚀 Future Roadmap (Pending)

While the core integration is complete, the following "Agentic" features are planned:

### Phase 2: Model Context Protocol (MCP) Integration
To prevent "hallucinations" (e.g., policies for non-existent buckets), we will integrate Tool Use.

1.  **Resource Validation Tool**:
    -   *Goal:* The LLM calls `verify_s3_bucket(name)` before writing the policy.
    -   *Behavior:* If the bucket is missing, the LLM asks the user for clarification instead of generating a broken policy.

2.  **Identity Awareness**:
    -   *Goal:* Pass the user's current identity context to the LLM to prevent self-escalation scenarios.

### Phase 3: Advanced Approval Workflows
-   **Slack Interactive Buttons:** Allow approvers to click "Approve" directly in Slack.
-   **Jira Integration:** Automatically create a ticket for "Critical" risk requests.