# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

## [2.0.0] - 2025-12-21

### 🚀 Major Features
-   **Gemini 3.0 Integration:** Switched default LLM engine to Google Gemini 3.0 Pro.
-   **Dual-Engine Architecture:** Introduced `llm_service.py` to support both Gemini and OpenAI (legacy) via configuration.
-   **UI Overhaul:** Completely redesigned `dynamicIAM_web.py` with a modern dashboard layout, sidebar history, and quick-action templates.

### 💅 User Experience
-   **Agentic Feedback:** Added `st.status` containers to visualize the AI's reasoning steps.
-   **Session History:** Users can now see a log of their recent requests and retrieve credentials from the sidebar.
-   **Visual Risk Scoring:** Risk scores are now displayed as prominent metrics with color-coded badges.

### ⚙️ Configuration
-   Added `LLM_PROVIDER`, `GOOGLE_API_KEY`, and `GEMINI_MODEL` to environment variables.
-   Added `google-generativeai` to `requirements.txt`.

### 🛡️ Security
-   Enhanced System Instructions for Gemini to strictly enforce JSON output and penalize wildcard permissions.
