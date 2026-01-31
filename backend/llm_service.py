"""
LLM Service Layer - Supports multiple AI providers for IAM policy generation

Providers supported:
- Google Gemini 3 Pro Preview (latest)
- OpenAI GPT-5 / o3-pro
- Anthropic Claude Opus 4.5
- Zhipu GLM-4.7

Sources:
- Gemini: https://blog.google/products-and-platforms/products/gemini/gemini-3/
- OpenAI: https://openai.com/index/introducing-o3-and-o4-mini/
- Anthropic: https://www.anthropic.com/news/claude-opus-4-5
- Zhipu: https://docs.z.ai/guides/llm/glm-4.7
"""
import os
import json
import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any

# Try to import google.genai (new package), fallback to google.generativeai (deprecated)
try:
    from google import genai
    GOOGLE_GENAI_NEW = True
except ImportError:
    try:
        import google.generativeai as genai
        GOOGLE_GENAI_NEW = False
        import warnings
        warnings.warn(
            "google.generativeai is deprecated. Please install google-genai: pip install google-genai",
            FutureWarning
        )
    except ImportError:
        genai = None
        GOOGLE_GENAI_NEW = False

import openai
import anthropic
from dotenv import load_dotenv

# Try to import zhipuai, but don't fail if not installed
try:
    from zhipuai import ZhipuAI
    ZHIPUAI_AVAILABLE = True
except ImportError:
    ZHIPUAI_AVAILABLE = False
    ZhipuAI = None

load_dotenv()

# Logger setup
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class PolicyResponse:
    """
    Response from LLM policy generation

    Attributes:
        policy: Generated IAM policy as dict
        risk: Risk level (low, medium, high, critical)
        explanation: Explanation of the risk assessment
        approver_note: Note for the approver
    """
    def __init__(self, policy: Dict[str, Any], risk: str, explanation: str, approver_note: str):
        self.policy = policy
        self.risk = risk
        self.explanation = explanation
        self.approver_note = approver_note


class LLMProvider(ABC):
    """Abstract base class for LLM providers"""

    @abstractmethod
    def generate_policy(self, request_text: str) -> PolicyResponse:
        """Generate an IAM policy from natural language request"""
        pass

    @abstractmethod
    def generate_rejection_guidance(self, original_request: str, policy: Dict[str, Any], risk: str) -> str:
        """Generate guidance for rejected requests to help user resubmit with better scoping"""
        pass


# System instruction for IAM policy generation
SYSTEM_INSTRUCTION = """You are a highly secure AWS IAM Policy Agent.
Your goal is to translate natural language requests into LEAST PRIVILEGE IAM Policies.

OUTPUT FORMAT:
You must respond with a VALID JSON object adhering to this schema:
{
  "policy": { ...valid IAM policy JSON... },
  "risk_score": "low" | "medium" | "high" | "critical",
  "explanation": "Brief explanation of permissions and risks.",
  "approver_note": "Recommendation for the approver."
}

RULES:
1. NO WILDCARDS ('*') on sensitive actions or resources unless absolutely necessary (score as HIGH/CRITICAL if present).
2. If the user requests access to a specific bucket/resource, limit the Resource field to that specific ARN.
3. If the request is vague, assume read-only or ask for clarification (but for this task, generate the safest interpretation).
4. Strictly follow valid JSON syntax. Do not wrap in markdown code blocks.
"""


class GeminiProvider(LLMProvider):
    """
    Google Gemini 3 Pro Preview provider

    Latest model: gemini-3-pro-preview-11-2025
    Source: https://blog.google/products-and-platforms/products/gemini/gemini-3/
    """

    def __init__(self):
        self.api_key = os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            logger.warning("GOOGLE_API_KEY not found. GeminiProvider may fail.")

        # Gemini 3 Pro Preview (released November 2025)
        # Model code: gemini-3-pro-preview
        self.model_name = os.getenv("GEMINI_MODEL", "gemini-3-pro-preview")

        # Initialize client based on API version
        if GOOGLE_GENAI_NEW:
            self.client = genai.Client(api_key=self.api_key)
        else:
            genai.configure(api_key=self.api_key)
            self.client = None

    def generate_policy(self, request_text: str) -> PolicyResponse:
        try:
            if GOOGLE_GENAI_NEW:
                # New google-genai API
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=f"User Request: {request_text}",
                    config=genai.types.GenerateContentConfig(
                        system_instruction=SYSTEM_INSTRUCTION,
                        response_mime_type="application/json"
                    )
                )
                response_text = response.text
            else:
                # Old google.generativeai API (deprecated)
                model = genai.GenerativeModel(
                    model_name=self.model_name,
                    system_instruction=SYSTEM_INSTRUCTION,
                    generation_config={"response_mime_type": "application/json"}
                )
                chat = model.start_chat(history=[])
                response = chat.send_message(f"User Request: {request_text}")
                response_text = response.text

            # Parse JSON
            data = json.loads(response_text)

            return PolicyResponse(
                policy=data.get("policy", {}),
                risk=data.get("risk_score", "medium"),
                explanation=data.get("explanation", "No explanation provided."),
                approver_note=data.get("approver_note", "")
            )
        except Exception as e:
            logger.error(f"Gemini generation error: {e}")
            raise e

    def generate_rejection_guidance(self, original_request: str, policy: Dict[str, Any], risk: str) -> str:
        """Generate guidance for rejected requests to help user resubmit with better scoping"""
        guidance_prompt = f"""The following AWS IAM access request was rejected due to elevated risk level ({risk}).

**Original Request:** "{original_request}"

**Generated Policy (high-risk):**
```json
{json.dumps(policy, indent=2)}
```

---

# 📋 Rejection Guidance

Please provide helpful guidance for the user to resubmit with a more appropriately scoped request. Format your response in **beautiful, well-spaced markdown** with emojis.

Use this structure with proper spacing:

## 1. 🔴 What Was Problematic

[Explain which specific permissions or resource ARNs caused the elevated risk assessment. Be specific about wildcards, overly broad actions, or sensitive services.]

---

## 2. ✨ Suggested Alternative Request

**Your improved request:**

> "[Rewritten, specific request that would be lower risk]"

**Why this works better:** [Brief explanation]

---

## 3. 💡 Tips for Better Scoping

- **Tip 1:** [Specific tip for this request type]
- **Tip 2:** [Another best practice]
- **Tip 3:** [Additional guidance]

---

## 4. 📝 Example of a Properly Scoped Request

### ❌ Instead of:
> "[Broad, risky request]"

### ✅ Submit this:
> "[Specific, well-scoped request with exact resources and limited actions]"

**Result:** Expected risk level and approval likelihood

---

**Remember:** The more specific you are about resources (exact ARNs) and actions (read-only vs write), the faster your request will be approved! 🚀"""

        try:
            if GOOGLE_GENAI_NEW:
                # New google-genai API
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=guidance_prompt
                )
                return response.text
            else:
                # Old google.generativeai API (deprecated)
                model = genai.GenerativeModel(model_name=self.model_name)
                response = model.generate_content(guidance_prompt)
                return response.text
        except Exception as e:
            logger.error(f"Gemini rejection guidance error: {e}")
            return "Unable to generate AI guidance. Please review your request and be more specific about resources and actions needed."


class OpenAIProvider(LLMProvider):
    """
    OpenAI provider - GPT-5 and o3-pro

    Latest models: gpt-5 (flagship), o3-pro (reasoning)
    Source: https://openai.com/index/introducing-o3-and-o4-mini/
    """

    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        # GPT-5.2 (latest) - GPT-5.1 and GPT-5 are previous models
        # Model code: gpt-5.2 (OpenAI recommends using latest)
        self.model_name = os.getenv("OPENAI_MODEL", "gpt-5.2")
        if self.api_key:
            self.client = openai.OpenAI(api_key=self.api_key)
        else:
            self.client = None
            logger.warning("OPENAI_API_KEY not found")

    def generate_policy(self, request_text: str) -> PolicyResponse:
        if not self.client:
            raise ValueError("OpenAI client not initialized. Check OPENAI_API_KEY.")

        prompt = f"""
You are a security agent that writes AWS IAM policies from user requests.
- ALWAYS create a policy that grants what is requested, scoped to least privilege.
- Respond with a JSON object.

Format:
{{
  "policy": {{ ... }},
  "risk_score": "low|medium|high|critical",
  "explanation": "...",
  "approver_note": "...",
  "suggested_refinement": "..."
}}

Request: "{request_text}"
"""
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                response_format={"type": "json_object"}
            )
            content = response.choices[0].message.content
            data = json.loads(content)

            return PolicyResponse(
                policy=data.get("policy", {}),
                risk=data.get("risk_score", "medium"),
                explanation=data.get("explanation", ""),
                approver_note=data.get("approver_note", ""),
                suggested_refinement=data.get("suggested_refinement", "")
            )
        except Exception as e:
            logger.error(f"OpenAI generation error: {e}")
            raise e

    def generate_rejection_guidance(self, original_request: str, policy: Dict[str, Any], risk: str) -> str:
        """Generate guidance for rejected requests to help user resubmit with better scoping"""
        if not self.client:
            return "OpenAI client not initialized. Please review your request and be more specific about resources and actions needed."

        guidance_prompt = f"""The following AWS IAM access request was rejected due to elevated risk level ({risk}).

Original Request: "{original_request}"

Generated Policy (high-risk): {json.dumps(policy, indent=2)}

Please provide helpful guidance for the user to resubmit with a more appropriately scoped request. Your response should include:

1. **What was problematic**: Explain which permissions or resource scopes caused the elevated risk assessment.
2. **Suggested alternative request**: A rewritten, more specific request that would be lower risk.
3. **Tips for better scoping**: Best practices for this type of access request.
4. **Example of a properly scoped request**: A concrete example.

Format your response as clear, actionable guidance with bullet points and sections."""

        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": guidance_prompt}],
                temperature=0.3
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"OpenAI rejection guidance error: {e}")
            return "Unable to generate AI guidance. Please review your request and be more specific about resources and actions needed."


class AnthropicProvider(LLMProvider):
    """
    Anthropic Claude provider - Opus 4.5

    Latest model: claude-opus-4-5 (released November 24, 2025)
    Source: https://www.anthropic.com/news/claude-opus-4-5
    """

    def __init__(self):
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        # Claude Opus 4.5 (released November 24, 2025)
        # Model code: claude-opus-4-5-20251101
        self.model_name = os.getenv("ANTHROPIC_MODEL", "claude-opus-4-5-20251101")
        if not self.api_key:
            logger.warning("ANTHROPIC_API_KEY not found. AnthropicProvider may fail.")

    def generate_policy(self, request_text: str) -> PolicyResponse:
        user_prompt = f"""User Request: "{request_text}"

Generate a least-privilege IAM policy for this request. Respond with ONLY a JSON object containing:
- policy: the IAM policy JSON
- risk_score: one of "low", "medium", "high", or "critical"
- explanation: brief explanation of the permissions
- approver_note: recommendation for the approver"""

        try:
            client = anthropic.Anthropic(api_key=self.api_key)
            response = client.messages.create(
                model=self.model_name,
                max_tokens=4096,
                system=SYSTEM_INSTRUCTION,
                messages=[{"role": "user", "content": user_prompt}],
                temperature=0.2
            )

            # Extract JSON from response
            content = response.content[0].text
            # Remove markdown code blocks if present
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            data = json.loads(content)

            return PolicyResponse(
                policy=data.get("policy", {}),
                risk=data.get("risk_score", "medium"),
                explanation=data.get("explanation", "No explanation provided."),
                approver_note=data.get("approver_note", "")
            )
        except Exception as e:
            logger.error(f"Anthropic generation error: {e}")
            raise e

    def generate_rejection_guidance(self, original_request: str, policy: Dict[str, Any], risk: str) -> str:
        """Generate guidance for rejected requests to help user resubmit with better scoping"""
        guidance_prompt = f"""The following AWS IAM access request was rejected due to elevated risk level ({risk}).

Original Request: "{original_request}"

Generated Policy (high-risk): {json.dumps(policy, indent=2)}

Please provide helpful guidance for the user to resubmit with a more appropriately scoped request. Your response should include:

1. **What was problematic**: Explain which permissions or resource scopes caused the elevated risk assessment.
2. **Suggested alternative request**: A rewritten, more specific request that would be lower risk.
3. **Tips for better scoping**: Best practices for this type of access request.
4. **Example of a properly scoped request**: A concrete example.

Format your response as clear, actionable guidance with bullet points and sections."""

        try:
            client = anthropic.Anthropic(api_key=self.api_key)
            response = client.messages.create(
                model=self.model_name,
                max_tokens=4096,
                messages=[{"role": "user", "content": guidance_prompt}],
                temperature=0.3
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"Anthropic rejection guidance error: {e}")
            return "Unable to generate AI guidance. Please review your request and be more specific about resources and actions needed."


class ZhipuProvider(LLMProvider):
    """
    Zhipu AI GLM provider - GLM-4.7

    Latest models: glm-4.7, glm-4.7-flash
    Source: https://docs.z.ai/guides/llm/glm-4.7
    """

    def __init__(self):
        self.api_key = os.getenv("ZHIPUAI_API_KEY")
        if not self.api_key:
            logger.warning("ZHIPUAI_API_KEY not found. ZhipuProvider may fail.")

        if not ZHIPUAI_AVAILABLE:
            raise ImportError(
                "zhipuai package is not installed. "
                "Install it with: pip install zhipuai"
            )

        # GLM-4.7 (December 2025) - latest flagship
        self.model_name = os.getenv("ZHIPUAI_MODEL", "glm-4.7")
        self.client = ZhipuAI(api_key=self.api_key)

    def generate_policy(self, request_text: str) -> PolicyResponse:
        prompt = f"""You are a security agent that writes AWS IAM policies from user requests.
- ALWAYS create a policy that grants what is requested, scoped to least privilege.
- Respond with a JSON object.

Format:
{{
  "policy": {{ ... }},
  "risk_score": "low|medium|high|critical",
  "explanation": "...",
  "approver_note": "..."
}}

Request: "{request_text}"

Respond ONLY with the JSON object, no additional text."""

        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": SYSTEM_INSTRUCTION},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                response_format={"type": "json_object"}
            )

            content = response.choices[0].message.content
            data = json.loads(content)

            return PolicyResponse(
                policy=data.get("policy", {}),
                risk=data.get("risk_score", "medium"),
                explanation=data.get("explanation", ""),
                approver_note=data.get("approver_note", "")
            )
        except Exception as e:
            logger.error(f"Zhipu generation error: {e}")
            raise e

    def generate_rejection_guidance(self, original_request: str, policy: Dict[str, Any], risk: str) -> str:
        """Generate guidance for rejected requests to help user resubmit with better scoping"""
        guidance_prompt = f"""The following AWS IAM access request was rejected due to elevated risk level ({risk}).

Original Request: "{original_request}"

Generated Policy (high-risk): {json.dumps(policy, indent=2)}

Please provide helpful guidance for the user to resubmit with a more appropriately scoped request. Your response should include:

1. **What was problematic**: Explain which permissions or resource scopes caused the elevated risk assessment.
2. **Suggested alternative request**: A rewritten, more specific request that would be lower risk.
3. **Tips for better scoping**: Best practices for this type of access request.
4. **Example of a properly scoped request**: A concrete example.

Format your response as clear, actionable guidance with bullet points and sections."""

        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are a helpful security assistant that provides clear guidance on AWS IAM access requests."},
                    {"role": "user", "content": guidance_prompt}
                ],
                temperature=0.3
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Zhipu rejection guidance error: {e}")
            return "Unable to generate AI guidance. Please review your request and be more specific about resources and actions needed."


def get_llm_provider(provider_type: str = None) -> LLMProvider:
    """
    Get the configured LLM provider instance

    Providers:
    - gemini: Google Gemini 3 Pro Preview
    - openai: OpenAI GPT-5 / o3-pro
    - anthropic/claude: Anthropic Claude Opus 4.5
    - zhipu/glm: Zhipu AI GLM-4.7

    Args:
        provider_type: Optional provider type to override environment variable

    Returns:
        LLMProvider instance
    """
    if provider_type is None:
        provider_type = os.getenv("LLM_PROVIDER", "gemini").lower()
    else:
        provider_type = provider_type.lower()

    if provider_type == "openai":
        return OpenAIProvider()
    elif provider_type in ("anthropic", "claude"):
        return AnthropicProvider()
    elif provider_type in ("zhipu", "glm"):
        return ZhipuProvider()
    elif provider_type == "gemini":
        return GeminiProvider()
    else:
        logger.warning(f"Unknown provider '{provider_type}', defaulting to Gemini")
        return GeminiProvider()
