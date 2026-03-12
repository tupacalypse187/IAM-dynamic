"""
Error Handler - Transforms API errors into user-friendly messages

Catches provider-specific errors and returns helpful, actionable guidance.
Uses string-based detection for better compatibility across provider library versions.
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class UserFacingError(Exception):
    """Base exception for user-facing errors with helpful messages"""

    def __init__(self, user_message: str, log_message: Optional[str] = None):
        self.user_message = user_message
        self.log_message = log_message or user_message
        super().__init__(self.user_message)


def handle_llm_error(error: Exception, provider: str) -> UserFacingError:
    """
    Transform LLM API errors into user-friendly messages.

    Args:
        error: The caught exception
        provider: The LLM provider name (gemini, openai, claude, zhipu)

    Returns:
        UserFacingError with a helpful message
    """
    error_str = str(error).lower()
    error_type = type(error).__name__
    error_module = type(error).__module__

    # Log the original error for debugging
    logger.error(f"{provider.upper()} API error: {error_module}.{error_type}: {error}")

    # --- Google Gemini Errors ---
    if provider == "gemini":
        # Check for ClientError from google.genai.errors
        if "clienterror" in error_type.lower() or "google" in error_module.lower():
            if "api key" in error_str or "apikey" in error_str or "invalid_argument" in error_str:
                return UserFacingError(
                    "🔑 **API Key Issue**\n\n"
                    "The Google API key is invalid or missing. Please:\n"
                    "1. Get a valid API key from [Google AI Studio](https://makersuite.google.com/app/apikey)\n"
                    "2. Set `GOOGLE_API_KEY=your-key` in your `.env` file\n"
                    "3. Restart the backend\n\n"
                    "[**Get API Key →**](https://makersuite.google.com/app/apikey)",
                    log_message=f"Gemini API key invalid: {error}"
                )
            if "quota" in error_str or "exceeded" in error_str or "rate limit" in error_str:
                return UserFacingError(
                    "⚠️ **API Quota Exceeded**\n\n"
                    "The Google Gemini API quota has been exceeded. Please:\n"
                    "1. Check your quota at [Google AI Studio](https://makersuite.google.com/app/apikey)\n"
                    "2. Wait for the quota to reset, or\n"
                    "3. Switch to a different provider (OpenAI, Claude, or Z.AI)",
                    log_message=f"Gemini quota exceeded: {error}"
                )
            if "model" in error_str and ("not found" in error_str or "does not exist" in error_str):
                return UserFacingError(
                    "🤖 **Model Not Found**\n\n"
                    "The requested model is not available. Please check the model name and try again.\n\n"
                    "Available models:\n"
                    "• `gemini-3.1-pro-preview` (recommended)\n"
                    "• `gemini-3-flash-preview`\n"
                    "• `gemini-3.1-flash-lite-preview`",
                    log_message=f"Gemini model not found: {error}"
                )

    # --- OpenAI Errors ---
    if provider == "openai":
        if "authentication" in error_str or "api key" in error_str or "401" in error_str:
            return UserFacingError(
                "🔑 **API Key Issue**\n\n"
                "The OpenAI API key is invalid or missing. Please:\n"
                "1. Get a valid API key from [OpenAI Platform](https://platform.openai.com/api-keys)\n"
                "2. Set `OPENAI_API_KEY=your-key` in your `.env` file\n"
                "3. Restart the backend\n\n"
                "[**Get API Key →**](https://platform.openai.com/api-keys)",
                log_message=f"OpenAI authentication error: {error}"
            )
        if "quota" in error_str or "limit" in error_str or "429" in error_str or "rate" in error_str:
            return UserFacingError(
                "⚠️ **Rate Limit Exceeded**\n\n"
                "The OpenAI API rate limit has been reached. Please:\n"
                "1. Wait a moment and try again\n"
                "2. Check your usage at [OpenAI Dashboard](https://platform.openai.com/usage)\n"
                "3. Try a different provider",
                log_message=f"OpenAI rate limit: {error}"
            )
        if "model" in error_str and ("not found" in error_str or "does not exist" in error_str):
            return UserFacingError(
                "🤖 **Model Not Found**\n\n"
                "The requested model is not available. Please check the model name and try again.\n\n"
                "Available models:\n"
                "• `gpt-5.3` (recommended)\n"
                "• `gpt-5-mini-2025-08-07`\n"
                "• `gpt-4o`\n"
                "• `gpt-4o-mini`",
                log_message=f"OpenAI model not found: {error}"
            )

    # --- Anthropic Claude Errors ---
    if provider == "claude" or provider == "anthropic":
        if "api key" in error_str or "apikey" in error_str or "401" in error_str or "unauthorized" in error_str:
            return UserFacingError(
                "🔑 **API Key Issue**\n\n"
                "The Anthropic API key is invalid or missing. Please:\n"
                "1. Get a valid API key from [Anthropic Console](https://console.anthropic.com/)\n"
                "2. Set `ANTHROPIC_API_KEY=your-key` in your `.env` file\n"
                "3. Restart the backend\n\n"
                "[**Get API Key →**](https://console.anthropic.com/)",
                log_message=f"Claude authentication error: {error}"
            )
        if ("rate" in error_str and "limit" in error_str) or "429" in error_str:
            return UserFacingError(
                "⚠️ **Rate Limit Exceeded**\n\n"
                "The Anthropic API rate limit has been reached. Please:\n"
                "1. Wait a moment and try again\n"
                "2. Check your usage\n"
                "3. Try a different provider",
                log_message=f"Claude rate limit: {error}"
            )
        if "timeout" in error_str or "timed out" in error_str:
            return UserFacingError(
                "⏱️ **Request Timeout**\n\n"
                "The request to Anthropic timed out. Please:\n"
                "1. Try again with a shorter request\n"
                "2. Check your network connection\n"
                "3. Try a different provider",
                log_message=f"Claude timeout: {error}"
            )
        if "connection" in error_str or "network" in error_str:
            return UserFacingError(
                "🔌 **Connection Error**\n\n"
                "Unable to reach the Anthropic API. Please:\n"
                "1. Check your internet connection\n"
                "2. Try again in a moment\n"
                "3. Check [Anthropic Status](https://status.anthropic.com/)",
                log_message=f"Claude connection error: {error}"
            )

    # --- Zhipu/GLM Errors ---
    if provider == "zhipu" or provider == "glm":
        if "api key" in error_str or "apikey" in error_str or "401" in error_str or "unauthorized" in error_str:
            return UserFacingError(
                "🔑 **API Key Issue**\n\n"
                "The Z.AI API key is invalid or missing. Please:\n"
                "1. Get a valid API key from [Z.AI Platform](https://api.z.ai)\n"
                "2. Set `ZAI_API_KEY=your-key` in your `.env` file\n"
                "3. Restart the backend\n\n"
                "[**Get API Key →**](https://api.z.ai)",
                log_message=f"Zhipu authentication error: {error}"
            )
        if "quota" in error_str or "limit" in error_str or "429" in error_str or "rate" in error_str:
            return UserFacingError(
                "⚠️ **Rate Limit Exceeded**\n\n"
                "The Z.AI API rate limit has been reached. Please:\n"
                "1. Wait a moment and try again\n"
                "2. Check your usage\n"
                "3. Try a different provider",
                log_message=f"Zhipu rate limit: {error}"
            )

    # --- Generic Errors by Message Content ---
    if "api key" in error_str or "apikey" in error_str:
        return UserFacingError(
            "🔑 **API Key Missing or Invalid**\n\n"
            f"The {provider.upper()} API key is not configured or is invalid. Please:\n"
            f"1. Add a valid API key to your `.env` file\n"
            f"2. Restart the backend",
            log_message=f"{provider} API key invalid: {error}"
        )

    if "quota" in error_str or "limit" in error_str or "exceeded" in error_str:
        return UserFacingError(
            "⚠️ **API Limit Reached**\n\n"
            f"The {provider.upper()} API quota/limit has been reached. Please:\n"
            "1. Wait and try again later\n"
            "2. Check your provider dashboard\n"
            "3. Try a different provider",
            log_message=f"{provider} quota error: {error}"
        )

    if "timeout" in error_str or "timed out" in error_str:
        return UserFacingError(
            "⏱️ **Request Timeout**\n\n"
            "The API request timed out. Please:\n"
            "1. Try again\n"
            "2. Check your network connection\n"
            "3. Try a different provider",
            log_message=f"{provider} timeout: {error}"
        )

    if "connection" in error_str or "network" in error_str:
        return UserFacingError(
            "🔌 **Connection Error**\n\n"
            "Unable to reach the API. Please:\n"
            "1. Check your internet connection\n"
            "2. Try again in a moment\n"
            "3. Try a different provider",
            log_message=f"{provider} connection error: {error}"
        )

    # --- Catch-all for unknown errors ---
    return UserFacingError(
        "❌ **Unable to Generate Policy**\n\n"
        f"The {provider.upper()} API encountered an unexpected error. Please:\n"
        "1. Try again\n"
        "2. Check that your API key is valid\n"
        "3. Try switching to a different provider\n\n"
        f"_Error: {error_type}_",
        log_message=f"{provider} unexpected error: {error}"
    )
