"""
Centralized configuration with pydantic validation

Supports LLM providers:
- Google Gemini 3.1 Pro Preview (gemini-3.1-pro-preview)
- OpenAI GPT-5.6 (gpt-5.6)
- Anthropic Claude Opus 5 (claude-opus-5)
- Zhipu GLM-5.3 (glm-5.3)
- Meta Muse (muse-spark-1.3-contributor)
- OpenRouter gateway (z-ai/glm-5.3)

Sources:
- Gemini: https://ai.google.dev/gemini-api/docs/models
- OpenAI: https://developers.openai.com/api/docs/models
- Anthropic: https://platform.claude.com/docs/en/docs/about-claude/models/overview
- Zhipu: https://docs.z.ai/guides/llm/glm-5.3
- Meta Muse: https://ai.developer.meta.com/docs/overview/
- OpenRouter: https://openrouter.ai/docs
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

    # Gemini (Google)
    google_api_key: Optional[str] = Field(default=None, env="GOOGLE_API_KEY")
    gemini_model: str = Field(default="gemini-3.1-pro-preview", env="GEMINI_MODEL")

    # OpenAI
    openai_api_key: Optional[str] = Field(default=None, env="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-5.6", env="OPENAI_MODEL")

    # Anthropic
    anthropic_api_key: Optional[str] = Field(default=None, env="ANTHROPIC_API_KEY")
    anthropic_model: str = Field(default="claude-opus-5", env="ANTHROPIC_MODEL")

    # Z.AI GLM (Global platform via api.z.ai)
    zai_api_key: Optional[str] = Field(default=None, env="ZAI_API_KEY")
    zai_model: str = Field(default="glm-5.3", env="ZAI_MODEL")

    # Meta Muse (Meta Model API via api.meta.ai)
    muse_api_key: Optional[str] = Field(default=None, env="MUSE_API_KEY")
    muse_model: str = Field(default="muse-spark-1.3-contributor", env="MUSE_MODEL")

    # OpenRouter (gateway - one key for many vendors' models)
    openrouter_api_key: Optional[str] = Field(default=None, env="OPENROUTER_API_KEY")
    openrouter_model: str = Field(default="z-ai/glm-5.3", env="OPENROUTER_MODEL")

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v: str) -> str:
        """Validate LLM provider is supported"""
        valid_providers = {
            "gemini", "openai", "anthropic", "claude",
            "zhipu", "glm", "muse", "meta", "openrouter",
        }
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


class TelegramConfig(BaseModel):
    """Telegram bot integration configuration"""
    # Bot API token from @BotFather (https://t.me/BotFather)
    bot_token: Optional[str] = Field(default=None, env="TELEGRAM_BOT_TOKEN")
    # Chat ID of the user/group receiving notifications
    chat_id: Optional[str] = Field(default=None, env="TELEGRAM_CHAT_ID")

    @property
    def enabled(self) -> bool:
        """Telegram notifications require both the token and the chat ID"""
        return bool(self.bot_token and self.chat_id)


class AppConfig(BaseModel):
    """Main application configuration"""
    aws: AWSConfig
    llm: LLMConfig
    slack: SlackConfig
    telegram: TelegramConfig
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
            gemini_model=os.getenv("GEMINI_MODEL", "gemini-3.1-pro-preview"),
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            openai_model=os.getenv("OPENAI_MODEL", "gpt-5.6"),
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
            anthropic_model=os.getenv("ANTHROPIC_MODEL", "claude-opus-5"),
            zai_api_key=os.getenv("ZAI_API_KEY"),
            zai_model=os.getenv("ZAI_MODEL", "glm-5.3"),
            muse_api_key=os.getenv("MUSE_API_KEY"),
            muse_model=os.getenv("MUSE_MODEL", "muse-spark-1.3-contributor"),
            openrouter_api_key=os.getenv("OPENROUTER_API_KEY"),
            openrouter_model=os.getenv("OPENROUTER_MODEL", "z-ai/glm-5.3")
        )

        slack_config = SlackConfig(
            webhook_url=os.getenv("SLACK_WEBHOOK_URL")
        )

        telegram_config = TelegramConfig(
            bot_token=os.getenv("TELEGRAM_BOT_TOKEN"),
            chat_id=os.getenv("TELEGRAM_CHAT_ID")
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
            telegram=telegram_config,
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
