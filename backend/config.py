"""
Centralized configuration with pydantic validation

Supports LLM providers:
- Google Gemini 3 Pro Preview (gemini-3-pro-preview-11-2025)
- OpenAI GPT-5 (gpt-5) and o3-pro
- Anthropic Claude Opus 4.5 (claude-opus-4-5)
- Zhipu GLM-4.7 (glm-4.7)

Sources:
- Gemini: https://blog.google/products-and-platforms/products/gemini/gemini-3/
- OpenAI: https://openai.com/index/introducing-o3-and-o4-mini/
- Anthropic: https://www.anthropic.com/news/claude-opus-4-5
- Zhipu: https://docs.z.ai/guides/llm/glm-4.7
"""
import os
import logging
from typing import Optional
from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator, model_validator

load_dotenv()

logger = logging.getLogger(__name__)


class AWSConfig(BaseModel):
    """AWS configuration"""
    account_id: str = Field(..., env="AWS_ACCOUNT_ID")
    role_name: str = Field(default="AgentPOCSessionRole", env="AWS_ROLE_NAME")

    @property
    def role_arn(self) -> str:
        """Construct role ARN from account ID and role name"""
        return f"arn:aws:iam::{self.account_id}:role/{self.role_name}"


class LLMConfig(BaseModel):
    """LLM provider configuration"""
    provider: str = Field(default="gemini", env="LLM_PROVIDER")

    # Gemini (Google) - Gemini 3 Pro Preview (November 2025)
    google_api_key: Optional[str] = Field(default=None, env="GOOGLE_API_KEY")
    gemini_model: str = Field(default="gemini-3-pro-preview", env="GEMINI_MODEL")

    # OpenAI - GPT-5.1 (latest) - GPT-5 is previous model
    openai_api_key: Optional[str] = Field(default=None, env="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-5.1", env="OPENAI_MODEL")

    # Anthropic - Claude Opus 4.5 (November 24, 2025)
    anthropic_api_key: Optional[str] = Field(default=None, env="ANTHROPIC_API_KEY")
    anthropic_model: str = Field(default="claude-opus-4-5-20251101", env="ANTHROPIC_MODEL")

    # Zhipu - GLM-4.7 (December 2025)
    zhipuai_api_key: Optional[str] = Field(default=None, env="ZHIPUAI_API_KEY")
    glm_model: str = Field(default="glm-4.7", env="ZHIPUAI_MODEL")

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v: str) -> str:
        """Validate LLM provider is supported"""
        valid_providers = {"gemini", "openai", "anthropic", "claude", "zhipu", "glm"}
        if v.lower() not in valid_providers:
            logger.warning(f"Unknown LLM provider '{v}', defaulting to 'gemini'")
            return "gemini"
        return v.lower()


class AuthConfig(BaseModel):
    """Authentication configuration"""
    admin_username: str = Field(default="admin")
    admin_password_hash: str = Field(default="")
    jwt_secret: str = Field(default="")
    jwt_expiry_hours: int = Field(default=8)
    turnstile_secret_key: Optional[str] = Field(default=None)

    @property
    def enabled(self) -> bool:
        """Auth is enabled only when a password hash is configured"""
        return bool(self.admin_password_hash)

    @model_validator(mode="after")
    def validate_jwt_secret_when_enabled(self) -> "AuthConfig":
        """Require JWT_SECRET when auth is enabled to prevent signing with empty string"""
        if self.admin_password_hash and not self.jwt_secret:
            raise ValueError("JWT_SECRET must be set when AUTH_PASSWORD_HASH is configured")
        return self


class SlackConfig(BaseModel):
    """Slack integration configuration"""
    webhook_url: Optional[str] = Field(default=None, env="SLACK_WEBHOOK_URL")


class AppConfig(BaseModel):
    """Main application configuration"""
    aws: AWSConfig
    llm: LLMConfig
    slack: SlackConfig
    auth: AuthConfig
    approver_name: str = Field(default="Admin", env="APPROVER_NAME")

    class Config:
        env_nested_delimiter = "__"


def load_config() -> AppConfig:
    """
    Load and validate configuration from environment

    Returns:
        AppConfig: Validated configuration object
    """
    try:
        # Extract environment variables for each config section
        aws_config = AWSConfig(
            account_id=os.getenv("AWS_ACCOUNT_ID"),
            role_name=os.getenv("AWS_ROLE_NAME", "AgentPOCSessionRole")
        )

        llm_config = LLMConfig(
            provider=os.getenv("LLM_PROVIDER", "gemini"),
            google_api_key=os.getenv("GOOGLE_API_KEY"),
            gemini_model=os.getenv("GEMINI_MODEL", "gemini-3-pro-preview-11-2025"),
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            openai_model=os.getenv("OPENAI_MODEL", "gpt-5"),
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
            anthropic_model=os.getenv("ANTHROPIC_MODEL", "claude-opus-4-5"),
            zhipuai_api_key=os.getenv("ZHIPUAI_API_KEY"),
            glm_model=os.getenv("ZHIPUAI_MODEL", "glm-4.7")
        )

        slack_config = SlackConfig(
            webhook_url=os.getenv("SLACK_WEBHOOK_URL")
        )

        auth_config = AuthConfig(
            admin_username=os.getenv("AUTH_USERNAME", "admin"),
            admin_password_hash=os.getenv("AUTH_PASSWORD_HASH", ""),
            jwt_secret=os.getenv("JWT_SECRET", ""),
            jwt_expiry_hours=int(os.getenv("JWT_EXPIRY_HOURS", "8")),
            turnstile_secret_key=os.getenv("TURNSTILE_SECRET_KEY"),
        )

        config = AppConfig(
            aws=aws_config,
            llm=llm_config,
            slack=slack_config,
            auth=auth_config,
            approver_name=os.getenv("APPROVER_NAME", "Admin")
        )

        logger.info(f"Configuration loaded successfully. LLM Provider: {config.llm.provider}")
        return config

    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        raise


# Singleton instance - imported by other modules
config = load_config()
