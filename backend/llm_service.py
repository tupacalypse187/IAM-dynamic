"""
LLM Service Layer - Supports multiple AI providers for IAM policy generation

Providers supported:
- Google Gemini 3.1 Pro Preview
- OpenAI GPT-5.4
- Anthropic Claude Opus 4.6
- Zhipu GLM-5 (via api.z.ai global platform)

Sources:
- Gemini: https://ai.google.dev/api/models
- OpenAI: https://platform.openai.com/docs/models
- Anthropic: https://docs.anthropic.com/en/docs/models-overview
- Zhipu: https://docs.z.ai/guides/llm/glm-5
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

import openai
import anthropic
from dotenv import load_dotenv

load_dotenv()

# Logger setup
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


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
- Use: `code` (with actual backticks, not \`)
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
    Google Gemini 3 Pro Preview provider

    Latest model: gemini-3-pro-preview-11-2025
    Source: https://blog.google/products-and-platforms/products/gemini/gemini-3/
    """

    def __init__(self):
        self.api_key = os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            logger.warning("GOOGLE_API_KEY not found. GeminiProvider may fail.")

        # Gemini 3.1 Pro Preview (released February 2026)
        # Model code: gemini-3.1-pro-preview
        self.model_name = os.getenv("GEMINI_MODEL", "gemini-3.1-pro-preview")

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
        self.model_name = os.getenv("OPENAI_MODEL", "gpt-5.3")
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
                approver_note=data.get("approver_note", "")
            )
        except Exception as e:
            logger.error(f"OpenAI generation error: {e}")
            raise e

    def generate_rejection_guidance(self, original_request: str, policy: Dict[str, Any], risk: str) -> str:
        """Generate guidance for rejected requests to help user resubmit with better scoping"""
        if not self.client:
            return "OpenAI client not initialized. Please review your request and be more specific about resources and actions needed."

        guidance_prompt = _build_rejection_guidance_prompt(original_request, policy, risk)

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
    Anthropic Claude provider - Opus 4.6

    Latest model: claude-opus-4-6
    Source: https://www.anthropic.com/news/claude-opus-4-5
    """

    def __init__(self):
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        # Claude Opus 4.6 (February 2026)
        self.model_name = os.getenv("ANTHROPIC_MODEL", "claude-opus-4-6")
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
        guidance_prompt = _build_rejection_guidance_prompt(original_request, policy, risk)

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
    Zhipu AI GLM provider - Global platform (api.z.ai)

    Uses OpenAI-compatible API.
    Latest models: glm-5, glm-4.7, glm-4.7-flash
    Source: https://docs.z.ai/guides/llm/glm-5
    """

    def __init__(self):
        from openai import OpenAI

        self.api_key = os.getenv("ZAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "ZAI_API_KEY not found. Set it in your .env file. "
                "Get your API key at: https://api.z.ai"
            )

        self.model_name = os.getenv("ZAI_MODEL", "glm-5")
        self.client = OpenAI(
            api_key=self.api_key,
            base_url="https://api.z.ai/api/coding/paas/v4/"
        )
        logger.info(f"Using Zhipu global platform (api.z.ai) with model {self.model_name}")

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
        guidance_prompt = _build_rejection_guidance_prompt(original_request, policy, risk)

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


def get_llm_provider(provider_type: str = None, model: str = None) -> LLMProvider:
    """
    Get the configured LLM provider instance

    Providers:
    - gemini: Google Gemini 3.1 Pro Preview
    - openai: OpenAI GPT-5.4
    - anthropic/claude: Anthropic Claude Opus 4.6
    - zhipu/glm: Zhipu AI GLM-5

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
