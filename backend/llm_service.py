"""
LLM Service Layer - Supports multiple AI providers for IAM policy generation

Providers supported:
- Google Gemini 3.1 Pro Preview (gemini-3.1-pro-preview)
- OpenAI GPT-5.6 family (gpt-5.6)
- Anthropic Claude Opus 5 (claude-opus-5)
- Z.AI GLM-5.3 (glm-5.3, via api.z.ai global platform)
- Meta Muse (muse-spark-1.3, via api.meta.ai Meta Model API)
- OpenRouter gateway (vendor/model slugs, e.g. z-ai/glm-5.3)

Sources:
- Gemini: https://ai.google.dev/api/models
- OpenAI: https://developers.openai.com/api/docs/models
- Anthropic: https://platform.claude.com/docs/en/docs/about-claude/models/overview
- Zhipu: https://docs.z.ai/guides/llm/glm-5.3
- Meta Muse: https://ai.developer.meta.com/docs/overview/
- OpenRouter: https://openrouter.ai/docs
"""
import os
import json
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any

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

# Try to import google.api_core exceptions (optional)
try:
    from google.api_core import exceptions as google_exceptions
except ImportError:
    google_exceptions = None

import openai
import anthropic
from dotenv import load_dotenv

# Import error handler
from services.error_handler import handle_llm_error, UserFacingError

load_dotenv()

# Logger setup
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Shown to users when guidance generation fails for any provider
FALLBACK_GUIDANCE = (
    "Unable to generate AI guidance. Please review your request and be more "
    "specific about resources and actions needed."
)


# AWS Service name mappings for dynamic guidance
AWS_SERVICE_NAMES = {
    "s3": "Amazon S3",
    "ec2": "Amazon EC2",
    "lambda": "AWS Lambda",
    "rds": "Amazon RDS",
    "dynamodb": "Amazon DynamoDB",
    "sns": "Amazon SNS",
    "sqs": "Amazon SQS",
    "iam": "AWS IAM",
    "kms": "AWS KMS",
    "secretsmanager": "AWS Secrets Manager",
    "cloudwatch": "Amazon CloudWatch",
    "logs": "Amazon CloudWatch Logs",
    "ecs": "Amazon ECS",
    "eks": "Amazon EKS",
    "eks-auth": "Amazon EKS",
    "ecr": "Amazon ECR",
    "apigateway": "Amazon API Gateway",
    "execute-api": "Amazon API Gateway",
    "cloudfront": "Amazon CloudFront",
    "route53": "Amazon Route 53",
    "elasticloadbalancing": "Elastic Load Balancing",
    "autoscaling": "AWS Auto Scaling",
    "cognito-idp": "Amazon Cognito",
    "cognito-identity": "Amazon Cognito",
    "kinesis": "Amazon Kinesis",
    "firehose": "Amazon Kinesis Data Firehose",
    "athena": "Amazon Athena",
    "glue": "AWS Glue",
    "sagemaker": "Amazon SageMaker",
    "bedrock": "Amazon Bedrock",
    "eventbridge": "Amazon EventBridge",
    "events": "Amazon EventBridge",
    "stepfunctions": "AWS Step Functions",
    "states": "AWS Step Functions",
    "ssm": "AWS Systems Manager",
    "ec2messages": "AWS Systems Manager",
    "ssmmessages": "AWS Systems Manager",
}


def _extract_services_from_policy(policy: Dict[str, Any]) -> list[str]:
    """
    Extract AWS service names from policy actions.

    Args:
        policy: IAM policy dictionary

    Returns:
        List of human-readable service names
    """
    services = set()

    for statement in policy.get("Statement", []):
        actions = statement.get("Action", [])
        if isinstance(actions, str):
            actions = [actions]

        for action in actions:
            if ":" in action:
                service_prefix = action.split(":")[0].lower()
                # Look up the friendly name, or format the prefix nicely
                friendly_name = AWS_SERVICE_NAMES.get(
                    service_prefix,
                    service_prefix.replace("-", " ").replace("_", " ").title()
                )
                services.add(friendly_name)

    return sorted(list(services))


def _build_rejection_guidance_prompt(
    original_request: str,
    policy: Dict[str, Any],
    risk: str
) -> str:
    """
    Build a dynamic guidance prompt tailored to the specific request.

    Analyzes the policy to provide service-specific guidance instead of
    using a hardcoded S3 example.

    Args:
        original_request: The user's natural language request
        policy: The generated IAM policy that was rejected
        risk: The risk level (low, medium, high, critical)

    Returns:
        A tailored prompt string for the LLM
    """
    # Extract AWS services from the policy
    services = _extract_services_from_policy(policy)
    services_str = " / ".join(services) if services else "AWS"

    return f"""Analyze this rejected AWS IAM access request and provide personalized guidance.

**Original Request:** "{original_request}"
**Risk Level:** {risk}

**Generated Policy:**
```json
{json.dumps(policy, indent=2)}
```

---

Based on this specific request for **{services_str}** access, provide helpful guidance that:

## 1. 🔴 Identify the Specific Issues

Point out the exact problems in this request that caused the **{risk}** risk rating:
- Which wildcards, overly broad actions, or sensitive permissions are problematic?
- Reference specific policy statements from the generated policy above
- Be concrete - cite the actual Action and Resource values

## 2. ✨ Suggest a Rewritten Request

Write a better version of their request that would likely get approved:
- Write it as the user would naturally say it (conversational, not technical)
- Make it specific to the resources and actions they actually need
- Keep it focused on **{services_str}** - their actual use case

## 3. 💡 Provide Actionable Tips

Give tips that are relevant to **{services_str}**, not generic advice:
- What specific resource identifiers should they include?
- What read vs write distinctions matter for this service?
- Any service-specific scoping best practices?

## 4. 📝 Show a Relevant Example

Create a "bad vs good" example specifically for **{services_str}**:
- NOT a generic S3 example - must be about their service
- Show what an overly broad request looks like for this service
- Show what a properly scoped request looks like for the same service

Format your response in clear, well-spaced markdown with emojis for readability.
Be conversational and helpful, not robotic.

IMPORTANT: Output raw markdown directly. Do NOT escape quotes, backticks, or other special characters. For example:
- Use: "example text" (with actual quotes, not \" or \")
- Use: `code` (with actual backticks, not \\`)
- Do NOT wrap the entire response in code blocks"""


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
    Google Gemini provider

    Latest model: gemini-3.1-pro-preview (flagship)
    Source: https://ai.google.dev/gemini-api/docs/models
    """

    def __init__(self):
        self.api_key = os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            logger.warning("GOOGLE_API_KEY not found. GeminiProvider may fail.")

        # Gemini 3.1 Pro Preview (released February 2026)
        # Model code: gemini-3.1-pro-preview
        self.model_name = os.getenv("GEMINI_MODEL", "gemini-3.1-pro-preview")

        # Initialize client based on API version.
        # genai.Client raises on api_key=None, so only build it when present;
        # genai.configure() only exists in the deprecated google.generativeai SDK.
        if GOOGLE_GENAI_NEW:
            self.client = genai.Client(api_key=self.api_key) if self.api_key else None
        elif self.api_key:
            genai.configure(api_key=self.api_key)
            self.client = None
        else:
            self.client = None

    def generate_policy(self, request_text: str) -> PolicyResponse:
        if not self.api_key:
            raise UserFacingError(
                "🔑 **API Key Missing**\n\n"
                "The Google API key is not configured. Please:\n"
                "1. Get a valid API key from [Google AI Studio](https://makersuite.google.com/app/apikey)\n"
                "2. Set `GOOGLE_API_KEY=your-key` in your `.env` file\n"
                "3. Restart the backend\n\n"
                "[**Get API Key →**](https://makersuite.google.com/app/apikey)",
                log_message="Gemini API key not configured"
            )

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
        except UserFacingError:
            raise
        except Exception as e:
            raise handle_llm_error(e, "gemini")

    def generate_rejection_guidance(self, original_request: str, policy: Dict[str, Any], risk: str) -> str:
        """Generate guidance for rejected requests to help user resubmit with better scoping"""
        guidance_prompt = _build_rejection_guidance_prompt(original_request, policy, risk)

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


def _parse_json_content(content: str) -> Dict[str, Any]:
    """Parse an LLM response as JSON, tolerating markdown code fences."""
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0].strip()
    elif "```" in content:
        content = content.split("```")[1].split("```")[0].strip()
    return json.loads(content)


POLICY_PROMPT_TEMPLATE = """You are a security agent that writes AWS IAM policies from user requests.
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

GUIDANCE_SYSTEM_INSTRUCTION = (
    "You are a helpful security assistant that provides clear guidance on AWS IAM access requests."
)


class OpenAICompatibleProvider(LLMProvider):
    """
    Base class for providers that expose an OpenAI-compatible Chat Completions API.

    Subclasses declare their env var names, default model, base URL and the
    markdown instructions shown to the user when the API key is missing.
    """

    provider_key = "openai"  # key used for error mapping in handle_llm_error
    display_name = "OpenAI-compatible"
    api_key_env = "OPENAI_API_KEY"
    model_env = "OPENAI_MODEL"
    default_model = "gpt-5.6"
    base_url = None
    # Set False for gateways whose models may not accept response_format
    supports_json_response_format = True
    # Set False for models that only support the default temperature (e.g.
    # OpenAI's GPT-5 reasoning family rejects temperature != 1 with a 400)
    supports_temperature = True
    key_setup_instructions = (
        "🔑 **API Key Missing**\n\n"
        "The API key is not configured. Please set it in your `.env` file "
        "and restart the backend."
    )

    def __init__(self):
        self.api_key = os.getenv(self.api_key_env)
        self.model_name = os.getenv(self.model_env, self.default_model)
        if not self.api_key:
            logger.warning(f"{self.api_key_env} not found. {self.display_name} provider may fail.")
            self.client = None
        else:
            self.client = openai.OpenAI(api_key=self.api_key, base_url=self.base_url)
            logger.info(f"Using {self.display_name} with model {self.model_name}")

    def generate_policy(self, request_text: str) -> PolicyResponse:
        if not self.client:
            raise UserFacingError(
                self.key_setup_instructions,
                log_message=f"{self.display_name} API key not configured"
            )

        prompt = POLICY_PROMPT_TEMPLATE.format(request_text=request_text)

        try:
            request_kwargs = {
                "model": self.model_name,
                "messages": [
                    {"role": "system", "content": SYSTEM_INSTRUCTION},
                    {"role": "user", "content": prompt}
                ],
            }
            if self.supports_temperature:
                request_kwargs["temperature"] = 0.2
            if self.supports_json_response_format:
                request_kwargs["response_format"] = {"type": "json_object"}

            response = self.client.chat.completions.create(**request_kwargs)
            data = _parse_json_content(response.choices[0].message.content)

            return PolicyResponse(
                policy=data.get("policy", {}),
                risk=data.get("risk_score", "medium"),
                explanation=data.get("explanation", ""),
                approver_note=data.get("approver_note", "")
            )
        except UserFacingError:
            raise
        except Exception as e:
            raise handle_llm_error(e, self.provider_key)

    def generate_rejection_guidance(self, original_request: str, policy: Dict[str, Any], risk: str) -> str:
        """Generate guidance for rejected requests to help user resubmit with better scoping"""
        if not self.client:
            return FALLBACK_GUIDANCE

        guidance_prompt = _build_rejection_guidance_prompt(original_request, policy, risk)

        try:
            guidance_kwargs = {
                "model": self.model_name,
                "messages": [
                    {"role": "system", "content": GUIDANCE_SYSTEM_INSTRUCTION},
                    {"role": "user", "content": guidance_prompt}
                ],
            }
            if self.supports_temperature:
                guidance_kwargs["temperature"] = 0.3
            response = self.client.chat.completions.create(**guidance_kwargs)
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"{self.display_name} rejection guidance error: {e}")
            return FALLBACK_GUIDANCE


class OpenAIProvider(OpenAICompatibleProvider):
    """
    OpenAI provider - GPT-5.6 family

    Latest models: gpt-5.6 (Sol alias), gpt-5.6-terra, gpt-5.6-luna
    Source: https://developers.openai.com/api/docs/models
    """

    provider_key = "openai"
    display_name = "OpenAI"
    api_key_env = "OPENAI_API_KEY"
    model_env = "OPENAI_MODEL"
    default_model = "gpt-5.6"
    base_url = None
    # GPT-5 reasoning models only accept the default temperature (1)
    supports_temperature = False
    key_setup_instructions = (
        "🔑 **API Key Missing**\n\n"
        "The OpenAI API key is not configured. Please:\n"
        "1. Get a valid API key from [OpenAI Platform](https://platform.openai.com/api-keys)\n"
        "2. Set `OPENAI_API_KEY=your-key` in your `.env` file\n"
        "3. Restart the backend\n\n"
        "[**Get API Key →**](https://platform.openai.com/api-keys)"
    )


class AnthropicProvider(LLMProvider):
    """
    Anthropic Claude provider

    Latest model: claude-opus-5 (July 2026)
    Source: https://platform.claude.com/docs/en/docs/about-claude/models/overview
    """

    def __init__(self):
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        self.model_name = os.getenv("ANTHROPIC_MODEL", "claude-opus-5")
        if not self.api_key:
            logger.warning("ANTHROPIC_API_KEY not found. AnthropicProvider may fail.")
            self.client = None
        else:
            self.client = anthropic.Anthropic(api_key=self.api_key)

    def generate_policy(self, request_text: str) -> PolicyResponse:
        if not self.client:
            raise UserFacingError(
                "🔑 **API Key Missing**\n\n"
                "The Anthropic API key is not configured. Please:\n"
                "1. Get a valid API key from [Anthropic Console](https://console.anthropic.com/)\n"
                "2. Set `ANTHROPIC_API_KEY=your-key` in your `.env` file\n"
                "3. Restart the backend\n\n"
                "[**Get API Key →**](https://console.anthropic.com/)",
                log_message="Anthropic API key not configured"
            )

        user_prompt = f"""User Request: "{request_text}"

Generate a least-privilege IAM policy for this request. Respond with ONLY a JSON object containing:
- policy: the IAM policy JSON
- risk_score: one of "low", "medium", "high", or "critical"
- explanation: brief explanation of the permissions
- approver_note: recommendation for the approver"""

        try:
            response = self.client.messages.create(
                model=self.model_name,
                max_tokens=4096,
                system=SYSTEM_INSTRUCTION,
                messages=[{"role": "user", "content": user_prompt}],
                temperature=0.2
            )

            data = _parse_json_content(response.content[0].text)

            return PolicyResponse(
                policy=data.get("policy", {}),
                risk=data.get("risk_score", "medium"),
                explanation=data.get("explanation", "No explanation provided."),
                approver_note=data.get("approver_note", "")
            )
        except UserFacingError:
            raise
        except Exception as e:
            raise handle_llm_error(e, "claude")

    def generate_rejection_guidance(self, original_request: str, policy: Dict[str, Any], risk: str) -> str:
        """Generate guidance for rejected requests to help user resubmit with better scoping"""
        if not self.client:
            return FALLBACK_GUIDANCE

        guidance_prompt = _build_rejection_guidance_prompt(original_request, policy, risk)

        try:
            response = self.client.messages.create(
                model=self.model_name,
                max_tokens=4096,
                messages=[{"role": "user", "content": guidance_prompt}],
                temperature=0.3
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"Anthropic rejection guidance error: {e}")
            return FALLBACK_GUIDANCE


class ZhipuProvider(OpenAICompatibleProvider):
    """
    Z.AI GLM provider - Global platform (api.z.ai)

    Uses OpenAI-compatible API (coding endpoint).
    Latest models: glm-5.3, glm-5.3-flash
    Source: https://docs.z.ai/guides/llm/glm-5.3
    """

    provider_key = "zhipu"
    display_name = "Z.AI GLM (api.z.ai)"
    api_key_env = "ZAI_API_KEY"
    model_env = "ZAI_MODEL"
    default_model = "glm-5.3"
    base_url = "https://api.z.ai/api/coding/paas/v4/"
    key_setup_instructions = (
        "🔑 **API Key Missing**\n\n"
        "The Z.AI API key is not configured. Please:\n"
        "1. Get a valid API key from [Z.AI Platform](https://api.z.ai)\n"
        "2. Set `ZAI_API_KEY=your-key` in your `.env` file\n"
        "3. Restart the backend\n\n"
        "[**Get API Key →**](https://api.z.ai)"
    )


class MuseProvider(OpenAICompatibleProvider):
    """
    Meta Muse provider - Meta Model API (api.meta.ai)

    Uses the OpenAI-compatible Meta Model API.
    Latest models: muse-spark-1.3-contributor, muse-spark-1.3, muse-spark-1.2, muse-spark-1.1
    Source: https://ai.developer.meta.com/docs/overview/
    """

    provider_key = "muse"
    display_name = "Meta Muse (api.meta.ai)"
    api_key_env = "MUSE_API_KEY"
    model_env = "MUSE_MODEL"
    default_model = "muse-spark-1.3-contributor"
    base_url = "https://api.meta.ai/v1"
    # Meta's API accepts the OpenAI SDK surface, but response_format support is
    # not guaranteed across Muse tiers - rely on prompt + fence-stripping parse.
    supports_json_response_format = False
    key_setup_instructions = (
        "🔑 **API Key Missing**\n\n"
        "The Meta Model API key is not configured. Please:\n"
        "1. Create an API key at [Meta Model API](https://ai.developer.meta.com/)\n"
        "2. Set `MUSE_API_KEY=your-key` in your `.env` file\n"
        "3. Restart the backend\n\n"
        "[**Get API Key →**](https://ai.developer.meta.com/)"
    )


class OpenRouterProvider(OpenAICompatibleProvider):
    """
    OpenRouter gateway provider - one API key for many vendors' models

    Uses the OpenAI-compatible OpenRouter API. Models are `vendor/model`
    slugs, e.g. z-ai/glm-5.3 or anthropic/claude-opus-5.
    Source: https://openrouter.ai/docs
    """

    provider_key = "openrouter"
    display_name = "OpenRouter"
    api_key_env = "OPENROUTER_API_KEY"
    model_env = "OPENROUTER_MODEL"
    default_model = "z-ai/glm-5.3"
    base_url = "https://openrouter.ai/api/v1"
    # Slugs from many vendors route through here; not all accept
    # response_format or non-default temperature, so rely on the prompt
    # plus fence-stripping parse and the provider's default temperature.
    supports_json_response_format = False
    supports_temperature = False
    key_setup_instructions = (
        "🔑 **API Key Missing**\n\n"
        "The OpenRouter API key is not configured. Please:\n"
        "1. Get a valid API key from [OpenRouter](https://openrouter.ai/settings/keys)\n"
        "2. Set `OPENROUTER_API_KEY=your-key` in your `.env` file\n"
        "3. Restart the backend\n\n"
        "[**Get API Key →**](https://openrouter.ai/settings/keys)"
    )


def get_llm_provider(provider_type: str = None, model: str = None) -> LLMProvider:
    """
    Get the configured LLM provider instance

    Providers:
    - gemini: Google Gemini 3.1 Pro Preview
    - openai: OpenAI GPT-5.6
    - anthropic/claude: Anthropic Claude Opus 5
    - zhipu/glm: Z.AI GLM-5.3
    - muse/meta: Meta Muse Spark
    - openrouter: OpenRouter gateway (vendor/model slugs)

    Args:
        provider_type: Optional provider type to override environment variable
        model: Optional model name to override provider default

    Returns:
        LLMProvider instance
    """
    if provider_type is None:
        provider_type = os.getenv("LLM_PROVIDER", "gemini").lower()
    else:
        provider_type = provider_type.lower()

    if provider_type == "openai":
        provider = OpenAIProvider()
    elif provider_type in ("anthropic", "claude"):
        provider = AnthropicProvider()
    elif provider_type in ("zhipu", "glm"):
        provider = ZhipuProvider()
    elif provider_type in ("muse", "meta"):
        provider = MuseProvider()
    elif provider_type == "openrouter":
        provider = OpenRouterProvider()
    elif provider_type == "gemini":
        provider = GeminiProvider()
    else:
        logger.warning(f"Unknown provider '{provider_type}', defaulting to Gemini")
        provider = GeminiProvider()

    # Override model if specified
    if model:
        provider.model_name = model
        logger.info(f"Using model override: {model}")

    return provider
