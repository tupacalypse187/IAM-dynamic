"""
IAM-Dynamic Backend - FastAPI Application

AI-driven Just-In-Time AWS IAM access request portal.
Generates least-privilege IAM policies using LLM and issues temporary credentials via AWS STS.
"""
import os
import logging
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from dotenv import load_dotenv

# Load environment variables from parent directory
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import services
from services.sts_service import STSService, STSAssumeRoleError, select_base_role_class
from services.slack_service import SlackService
from services.telegram_service import TelegramService
from services.auth_service import AuthService, create_jwt, verify_jwt
from services.turnstile_service import TurnstileService
from services.user_store import UserStore, RegistrationError
from services.request_store import (
    RequestStore,
    RequestStoreError,
    STATUS_PENDING,
    STATUS_APPROVED,
)
from services.audit_log import AuditLog
from services.profile_store import ProfileStore, ProfileStoreError
from services.error_handler import UserFacingError
from llm_service import get_llm_provider, PolicyResponse
from config import load_config

# Load configuration
config = load_config()

# Initialize services
sts_service = STSService(config.aws.role_arn)
slack_service = SlackService(config.slack.webhook_url)
telegram_service = TelegramService(
    bot_token=config.telegram.bot_token,
    chat_id=config.telegram.chat_id,
)

# Auth services (optional — disabled when AUTH_PASSWORD_HASH is not set)
auth_service: Optional[AuthService] = None
turnstile_service = TurnstileService(config.auth.turnstile_secret_key)

if not config.auth.jwt_secret:
    # Dev convenience: sessions work without JWT_SECRET but don't survive
    # restarts. Production sets JWT_SECRET explicitly.
    config.auth.jwt_secret = secrets.token_hex(32)
    logger.warning("JWT_SECRET not set — using an ephemeral signing key")

if config.auth.enabled:
    auth_service = AuthService(
        username=config.auth.admin_username,
        password_hash=config.auth.admin_password_hash,
        jwt_secret=config.auth.jwt_secret,
        jwt_expiry_hours=config.auth.jwt_expiry_hours,
    )
    logger.info("Authentication enabled")
else:
    logger.info("Authentication disabled (no AUTH_PASSWORD_HASH configured)")

# Multi-user store for in-app registration (first user becomes admin).
# Built lazily so a bad AUTH_USERS_DB path degrades to legacy-only auth
# instead of killing startup.
user_store: Optional[UserStore] = None


def get_user_store() -> Optional[UserStore]:
    """Return the singleton user store, creating it on first use."""
    global user_store
    if user_store is None:
        db_path = config.auth.users_db_path
        if not os.path.isabs(db_path):
            db_path = str(Path(__file__).parent / db_path)
        try:
            user_store = UserStore(db_path)
        except Exception:
            logger.exception("User database unavailable at %s", db_path)
            user_store = None
    return user_store


# Access-request store and JSONL audit log for the review workflow.
# Built lazily like the user store so a bad path degrades to a 500 on
# the review endpoints instead of killing startup.
request_store: Optional[RequestStore] = None
audit_log: Optional[AuditLog] = None


def _resolve_data_path(configured: str) -> str:
    if os.path.isabs(configured):
        return configured
    return str(Path(__file__).parent / configured)


def get_request_store() -> Optional[RequestStore]:
    """Return the singleton request store, creating it on first use."""
    global request_store
    if request_store is None:
        db_path = _resolve_data_path(config.requests_db_path)
        try:
            request_store = RequestStore(db_path)
        except Exception:
            logger.exception("Request database unavailable at %s", db_path)
            request_store = None
    return request_store


def get_audit_log() -> Optional[AuditLog]:
    """Return the singleton JSONL audit log, creating it on first use."""
    global audit_log
    if audit_log is None:
        try:
            audit_log = AuditLog(_resolve_data_path(config.audit_log_path))
        except Exception:
            logger.exception("Audit log unavailable")
            audit_log = None
    return audit_log


def _require_request_store() -> RequestStore:
    store = get_request_store()
    if store is None:
        raise HTTPException(status_code=500, detail="Request database is unavailable")
    return store


# Per-user LLM profiles + admin-managed provider catalog.
profile_store: Optional[ProfileStore] = None


def _catalog_seed_entries() -> list[dict]:
    """Flatten PROVIDER_MODELS into catalog seed rows."""
    entries: list[dict] = []
    for provider_id, models in PROVIDER_MODELS.items():
        for model in models:
            entries.append({
                "provider": provider_id,
                "model": model["id"],
                "display_name": f"{model['name']}",
            })
    return entries


def get_profile_store() -> Optional[ProfileStore]:
    """Return the singleton profile store, creating + seeding it on first use."""
    global profile_store
    if profile_store is None:
        db_path = _resolve_data_path(config.profiles_db_path)
        secret = config.profile_encryption_key or config.auth.jwt_secret
        try:
            profile_store = ProfileStore(db_path, secret)
            profile_store.seed_catalog(_catalog_seed_entries())
        except Exception:
            logger.exception("Profile database unavailable at %s", db_path)
            profile_store = None
    return profile_store


def _require_profile_store() -> ProfileStore:
    store = get_profile_store()
    if store is None:
        raise HTTPException(status_code=500, detail="Profile database is unavailable")
    return store


def _actor_role(username: str) -> str:
    return "admin" if _is_admin(username) else "user"


def _select_base_role(policy: dict) -> tuple[Optional[str], str]:
    """Pick the least-privilege base role for a stored policy.

    Returns (role_arn_or_None, class_name). None means "no base roles
    configured" — the caller falls back to the legacy single role, so
    today's behavior is unchanged until ARNs are set (see aws/base-roles.md).
    The admin class is never auto-selected.
    """
    role_class = select_base_role_class(policy)
    arn = {
        "readonly": config.aws.base_role_readonly,
        "developer": config.aws.base_role_developer,
    }.get(role_class, "")
    if not arn:
        # Fall across: a read-only policy with only the developer base set
        # still gets a tighter base than the legacy role.
        arn = config.aws.base_role_developer or config.aws.base_role_readonly
        if arn:
            role_class = (
                "developer" if arn == config.aws.base_role_developer else "readonly"
            )
    if not arn:
        return None, "legacy"
    return arn, role_class


def _audit(
    event: str,
    *,
    request_id: int,
    actor: str,
    actor_role: Optional[str] = None,
    from_status: Optional[str] = None,
    to_status: Optional[str] = None,
    **extra,
) -> None:
    """Append an audit event; failures are logged, never fatal.

    Automated decisions (low-risk auto-approval) pass actor="system" with
    actor_role="automated" so requesters can tell a human reviewer apart
    from the system in the audit trail.
    """
    log = get_audit_log()
    if log is None:
        logger.error("Audit log unavailable — event %s not recorded", event)
        return
    try:
        log.append(
            event,
            request_id=request_id,
            actor=actor,
            actor_role=actor_role or _actor_role(actor),
            from_status=from_status,
            to_status=to_status,
            **extra,
        )
    except Exception:
        logger.exception("Failed to append audit event %s", event)


# --- Pydantic Models ---

class PolicyRequest(BaseModel):
    """Request model for policy generation"""
    request_text: str = Field(..., description="Natural language description of access needed", min_length=10)
    provider: Optional[str] = Field(default="gemini", description="LLM provider to use")
    model: Optional[str] = Field(default=None, description="Model to use (overrides provider default)")
    duration: int = Field(default=2, description="Requested session duration in hours", ge=1, le=12)
    change_case: Optional[str] = Field(default=None, description="Business justification for high-risk requests")
    profile_id: Optional[int] = Field(default=None, description="Your saved LLM profile to evaluate with (overrides provider/model)")


class PolicyResponseModel(BaseModel):
    """Response model for generated policy"""
    policy: dict
    risk: str
    explanation: str
    approver_note: str
    auto_approved: bool
    max_duration: int


class IssueCredentialsRequest(BaseModel):
    """Request model for credential issuance"""
    policy: dict
    duration: int = Field(..., ge=1, le=12)
    approved: bool = Field(default=False)
    approver: Optional[str] = Field(default=None)
    change_case: Optional[str] = Field(default=None)
    # Echo of the reviewed assessment from generate-policy: the notification
    # must report the actual risk, not a hardcoded default.
    risk: str = Field(default="medium")
    auto_approved: bool = Field(default=False)


class CredentialsResponse(BaseModel):
    """Response model for issued credentials"""
    access_key_id: str
    secret_access_key: str
    session_token: str
    expiration: str
    region: str = "us-east-1"


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    version: str
    timestamp: str


class LoginRequest(BaseModel):
    """Request model for authentication"""
    username: str
    password: str
    turnstile_token: Optional[str] = None


class LoginResponse(BaseModel):
    """Response model for successful login"""
    token: str
    expires_at: str
    username: str


class AuthStatusResponse(BaseModel):
    """Response for auth status check"""
    authenticated: bool
    username: Optional[str] = None
    auth_required: bool
    is_admin: bool = False


class RegisterRequest(BaseModel):
    """Request model for self-registration"""
    username: str
    password: str
    turnstile_token: Optional[str] = None


class RegisterResponse(LoginResponse):
    """Registration response — same session as login, plus admin flag"""
    is_admin: bool = False


class UserListResponse(BaseModel):
    """Admin user listing"""
    users: list


class SubmitAccessRequest(BaseModel):
    """Submit a new access request for LLM evaluation + review routing"""
    request_text: str = Field(..., description="Natural language description of access needed", min_length=10)
    provider: Optional[str] = Field(default="gemini", description="LLM provider to use")
    model: Optional[str] = Field(default=None, description="Model to use (overrides provider default)")
    duration: int = Field(default=2, description="Requested session duration in hours", ge=1, le=12)
    change_case: Optional[str] = Field(default=None, description="Business justification for high-risk requests")
    profile_id: Optional[int] = Field(default=None, description="Your saved LLM profile to evaluate with (overrides provider/model)")


class AccessRequestModel(BaseModel):
    """A persisted access request with its evaluated LLM response + review state"""
    id: int
    requester: str
    request_text: str
    provider: str
    model: Optional[str] = None
    duration: int
    policy: dict
    risk: str
    explanation: str
    approver_note: str
    auto_approved: bool
    status: str
    reviewer: Optional[str] = None
    feedback: Optional[str] = None
    revision: int = 1
    created_at: str
    updated_at: str
    decided_at: Optional[str] = None
    credentials_expires_at: Optional[str] = None


class ReviewAccessRequest(BaseModel):
    """Reviewer decision on a pending request"""
    decision: str = Field(..., description="One of: approve, deny, changes_requested")
    feedback: Optional[str] = Field(default=None, description="Required for deny and changes_requested")


class ResubmitAccessRequest(BaseModel):
    """Owner resubmission of a sent-back request (optionally edited)"""
    request_text: Optional[str] = Field(default=None, description="Edited request text (defaults to stored text)", min_length=10)
    provider: Optional[str] = Field(default=None, description="LLM provider to use (defaults to stored)")
    model: Optional[str] = Field(default=None, description="Model to use (overrides provider default)")
    duration: Optional[int] = Field(default=None, description="Requested session duration in hours", ge=1, le=12)
    profile_id: Optional[int] = Field(default=None, description="Your saved LLM profile to evaluate with (overrides provider/model)")


class AuditEventModel(BaseModel):
    """One JSONL audit trail record"""
    ts: str
    event: str
    request_id: int
    actor: str
    actor_role: str
    from_status: Optional[str] = None
    to_status: Optional[str] = None

    class Config:
        extra = "allow"


class CatalogEntryModel(BaseModel):
    """One admin-managed provider/model pair"""
    provider: str
    model: str
    display_name: str = ""
    enabled: bool


class CatalogUpdateBody(BaseModel):
    """Enable or disable a catalog pair (administrators only)"""
    provider: str
    model: str
    enabled: bool


class ProfileCreateBody(BaseModel):
    """Create a named LLM profile (key is encrypted at rest, never returned)"""
    name: str = Field(..., min_length=1, max_length=64)
    provider: str
    model: str
    api_key: str = Field(..., min_length=1)


class ProfileUpdateBody(BaseModel):
    """Rename a profile and/or replace its key"""
    name: Optional[str] = Field(default=None, min_length=1, max_length=64)
    api_key: Optional[str] = Field(default=None, min_length=1)


class ProfileModel(BaseModel):
    """A user's LLM profile — key material is never serialized"""
    id: int
    username: str
    name: str
    provider: str
    model: str
    has_key: bool
    key_hint: str = ""
    active: bool
    created_at: str
    updated_at: str


# --- Auth Helpers ---

def _auth_required() -> bool:
    """Auth is required with a legacy hash OR any registered users.

    A fresh install (no hash, no users) stays open so the first admin
    account can be created via registration.
    """
    if auth_service is not None:
        return True
    store = get_user_store()
    return store is not None and store.count_users() > 0


def _is_admin(username: Optional[str]) -> bool:
    """Legacy admin username or a store-flagged administrator."""
    if not username:
        return False
    if auth_service is not None and username == config.auth.admin_username:
        return True
    store = get_user_store()
    return store is not None and store.is_admin(username)

def _extract_token(request: Request) -> Optional[str]:
    """Extract JWT from Authorization header or session cookie."""
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]
    return request.cookies.get("iam_session")


async def get_current_user(request: Request) -> str:
    """
    Dependency that extracts and validates the current user.

    When auth is fully disabled (no AUTH_PASSWORD_HASH and no registered
    users), returns "admin" to preserve the existing local dev workflow.
    """
    if not _auth_required():
        return "admin"

    token = _extract_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    username = verify_jwt(token, config.auth.jwt_secret)
    if not username:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return username


# --- Lifespan Context Manager ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan"""
    logger.info("Starting IAM-Dynamic Backend API")
    yield
    logger.info("Shutting down IAM-Dynamic Backend API")


# --- FastAPI Application ---

app = FastAPI(
    title="IAM-Dynamic API",
    description="AI-driven Just-In-Time AWS IAM access request portal",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS — production domain derived from CADDY_DOMAIN env var
cors_origins = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "http://localhost:8080",
]
caddy_domain = os.getenv("CADDY_DOMAIN")
if caddy_domain:
    cors_origins.append(f"https://{caddy_domain}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Helper Functions ---

def get_max_duration(risk: str) -> int:
    """Get maximum allowed duration based on risk level"""
    return {"low": 12, "medium": 4, "high": 2, "critical": 1}.get(risk.lower(), 2)


# Deterministic server-side guardrail for credential issuance.
# Mirrors the desktop Agent_Kit lists in
# desktop/src/main/agentkit/audit-risk.ts. Runs before STS so a
# caller-asserted `approved` flag cannot self-approve a broad policy.
_ESCALATION_ACTIONS = frozenset(a.lower() for a in [
    "iam:PassRole",
    "iam:CreatePolicyVersion",
    "iam:SetDefaultPolicyVersion",
    "iam:AttachUserPolicy",
    "iam:AttachGroupPolicy",
    "iam:AttachRolePolicy",
    "iam:PutUserPolicy",
    "iam:PutGroupPolicy",
    "iam:PutRolePolicy",
    "iam:CreateAccessKey",
    "iam:CreateLoginProfile",
    "iam:UpdateAssumeRolePolicy",
    "sts:AssumeRole",
    "sts:AssumeRoleWithSAML",
    "glue:UpdateDevEndpoint",
    "lambda:UpdateFunctionCode",
])

_READ_ONLY_PREFIXES = tuple(p.lower() for p in [
    "s3:Get",
    "s3:List",
    "s3:Describe",
    "dynamodb:GetItem",
    "dynamodb:BatchGetItem",
    "dynamodb:Query",
    "dynamodb:Scan",
    "dynamodb:Describe",
    "ec2:Describe",
    "rds:Describe",
    "logs:Get",
    "logs:Describe",
    "logs:FilterLogEvents",
    "cloudwatch:Get",
    "cloudwatch:Describe",
    "cloudwatch:List",
])


def _as_str_list(value) -> list:
    """Normalize an IAM string-or-list field to a list of strings."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [v for v in value if isinstance(v, str)]
    return []


def _is_read_only_action(action: str) -> bool:
    """Check an action against the read-only prefix allowlist."""
    lowered = action.lower()
    return any(lowered.startswith(prefix) for prefix in _READ_ONLY_PREFIXES)


def find_overly_broad_policy_violation(policy: dict) -> Optional[str]:
    """Return a rejection reason when an Allow statement is overly broad.

    Missing Effect is treated as Allow. Deny statements are skipped.
    Returns None when the policy passes the guardrail.
    """
    if not isinstance(policy, dict):
        return "Policy must be an IAM policy document object."
    raw_statements = policy.get("Statement", [])
    statements = raw_statements if isinstance(raw_statements, list) else [raw_statements]
    for stmt in statements:
        if not isinstance(stmt, dict):
            continue
        effect = stmt.get("Effect", "Allow")
        if not isinstance(effect, str):
            effect = "Allow"
        if effect.lower() == "deny":
            continue
        if any(v.strip() for v in _as_str_list(stmt.get("NotAction"))):
            return (
                "NotAction is not allowed for credential issuance; "
                "request specific Action values instead."
            )
        if any(v.strip() for v in _as_str_list(stmt.get("NotResource"))):
            return (
                "NotResource is not allowed for credential issuance; "
                "request specific Resource values instead."
            )
        actions = _as_str_list(stmt.get("Action"))
        resources = _as_str_list(stmt.get("Resource"))
        for action in actions:
            if "*" in action:
                return (
                    f"Wildcard action '{action}' is not allowed for "
                    "credential issuance; request specific actions."
                )
            if action.lower() in _ESCALATION_ACTIONS:
                return (
                    f"Action '{action}' can enable privilege escalation "
                    "and is not allowed for credential issuance."
                )
        if "*" in resources and any(not _is_read_only_action(a) for a in actions):
            return (
                'Resource "*" is only allowed with read-only actions; '
                "scope the resource down to a specific ARN."
            )
    return None


# Available models per provider (updated October 2026)
PROVIDER_MODELS = {
    "gemini": [
        {"id": "gemini-4-argon", "name": "Gemini 4 Argon"},
        {"id": "gemini-3.8-flash", "name": "Gemini 3.8 Flash"},
        {"id": "gemini-3.6-flash", "name": "Gemini 3.6 Flash"},
        {"id": "gemini-3.5-flash-lite", "name": "Gemini 3.5 Flash Lite"},
    ],
    "openai": [
        {"id": "gpt-6-astra", "name": "GPT-6 Astra"},
        {"id": "gpt-6.1-sol", "name": "GPT-6.1 Sol"},
        {"id": "gpt-6.1-terra", "name": "GPT-6.1 Terra"},
        {"id": "gpt-6-luna", "name": "GPT-6 Luna"},
    ],
    "claude": [
        {"id": "claude-fable-5-1", "name": "Claude Fable 5.1"},
        {"id": "claude-opus-5-5", "name": "Claude Opus 5.5"},
        {"id": "claude-sonnet-5-5", "name": "Claude Sonnet 5.5"},
        {"id": "claude-haiku-5-5", "name": "Claude Haiku 5.5"},
    ],
    "zhipu": [
        {"id": "glm-5.3", "name": "GLM-5.3"},
        {"id": "glm-5.3-flash", "name": "GLM-5.3 Flash"},
        {"id": "glm-5.2", "name": "GLM-5.2"},
        {"id": "glm-5.1", "name": "GLM-5.1"},
        {"id": "glm-5", "name": "GLM-5"},
        {"id": "glm-4.7", "name": "GLM-4.7"},
    ],
    "muse": [
        {"id": "muse-wonder-1.0", "name": "Muse Wonder 1.0"},
        {"id": "muse-spark-1.3-contributor", "name": "Muse Spark 1.3 (Contributor)"},
        {"id": "muse-spark-1.3", "name": "Muse Spark 1.3"},
        {"id": "muse-spark-1.2", "name": "Muse Spark 1.2"},
        {"id": "muse-spark-1.1", "name": "Muse Spark 1.1"},
    ],
    "openrouter": [
        {"id": "z-ai/glm-5.3", "name": "GLM-5.3 (Z.AI)"},
        {"id": "z-ai/glm-5.3-flash", "name": "GLM-5.3 Flash (Z.AI)"},
        {"id": "openai/gpt-6-astra", "name": "GPT-6 Astra (OpenAI)"},
        {"id": "anthropic/claude-opus-5.5", "name": "Claude Opus 5.5 (Anthropic)"},
        {"id": "google/gemini-4-argon", "name": "Gemini 4 Argon (Google)"},
        {"id": "meta/muse-spark-1.3", "name": "Muse Spark 1.3 (Meta)"},
    ],
}


# Fast/cheap model tier for low-stakes tasks such as rejection guidance.
# Policy generation uses the user-selected (frontier) model; rejection
# guidance falls back to FAST_MODELS unless the caller pins a model.
FAST_MODELS = {
    "gemini": "gemini-3.8-flash",
    "openai": "gpt-6-luna",
    "claude": "claude-haiku-5-5",
    "zhipu": "glm-5.3-flash",
    "muse": "muse-spark-1.3-contributor",
    "openrouter": "z-ai/glm-5.3-flash",
}

# Aliases accepted by llm_service.get_llm_provider, resolved to the
# PROVIDER_MODELS catalog key before the FAST_MODELS lookup.
_PROVIDER_ALIASES = {
    "anthropic": "claude",
    "glm": "zhipu",
    "meta": "muse",
}


def fast_model_for(provider: str | None) -> str | None:
    """Return the fast-tier model for a provider, or None if unknown."""
    if not provider:
        return None
    key = _PROVIDER_ALIASES.get(provider.lower(), provider.lower())
    return FAST_MODELS.get(key)


def send_audit_notification(auto_approved: bool, req: str, risk: str, duration: int, approver: str = None):
    """
    Send audit notification to every configured channel (Slack, Telegram).

    Notification failures are logged but never fail the credential request.
    """
    try:
        slack_service.send_credential_notification(
            request_text=req,
            risk_level=risk,
            duration_hours=duration,
            auto_approved=auto_approved,
            approver=approver
        )
    except Exception as e:
        logger.error(f"Failed to send Slack notification: {e}")

    try:
        telegram_service.send_credential_notification(
            request_text=req,
            risk_level=risk,
            duration_hours=duration,
            auto_approved=auto_approved,
            approver=approver
        )
    except Exception as e:
        logger.error(f"Failed to send Telegram notification: {e}")


# --- API Endpoints ---

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        timestamp=datetime.now(timezone.utc).isoformat()
    )


# --- Auth Endpoints ---

@app.post("/api/auth/login", response_model=LoginResponse)
async def login(request: Request, body: LoginRequest):
    """Authenticate and return a JWT token."""
    if not _auth_required():
        raise HTTPException(status_code=404, detail="Authentication is not enabled")

    # Verify Turnstile CAPTCHA
    remote_ip = request.headers.get("x-real-ip", request.client.host if request.client else None)
    if not await turnstile_service.verify(body.turnstile_token, remote_ip):
        raise HTTPException(status_code=400, detail="CAPTCHA verification failed")

    store = get_user_store()
    if store is not None and store.verify(body.username, body.password):
        result = create_jwt(
            body.username, config.auth.jwt_secret, config.auth.jwt_expiry_hours
        )
    elif auth_service is not None:
        result = auth_service.authenticate(body.username, body.password)
    else:
        result = None
    if not result:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    return LoginResponse(
        token=result.token,
        expires_at=result.expires_at.isoformat(),
        username=body.username,
    )


@app.post("/api/auth/register", response_model=RegisterResponse, status_code=201)
async def register(request: Request, body: RegisterRequest):
    """Self-register a new account (first user becomes administrator).

    Disabled with AUTH_ALLOW_REGISTRATION=false for invite-only deployments.
    """
    if not config.auth.allow_registration:
        raise HTTPException(
            status_code=403,
            detail="Self-registration is disabled. Ask an administrator for an account.",
        )

    # Verify Turnstile CAPTCHA
    remote_ip = request.headers.get("x-real-ip", request.client.host if request.client else None)
    if not await turnstile_service.verify(body.turnstile_token, remote_ip):
        raise HTTPException(status_code=400, detail="CAPTCHA verification failed")

    store = get_user_store()
    if store is None:
        raise HTTPException(status_code=500, detail="User database is unavailable")

    try:
        user = store.register(body.username, body.password)
    except RegistrationError as e:
        status_code = 409 if e.code == "username_taken" else 400
        raise HTTPException(status_code=status_code, detail=str(e))

    result = create_jwt(
        user["username"], config.auth.jwt_secret, config.auth.jwt_expiry_hours
    )
    return RegisterResponse(
        token=result.token,
        expires_at=result.expires_at.isoformat(),
        username=user["username"],
        is_admin=user["is_admin"],
    )


@app.get("/api/auth/users", response_model=UserListResponse)
async def list_users(user: str = Depends(get_current_user)):
    """List registered users (administrators only)."""
    if not _is_admin(user):
        raise HTTPException(status_code=403, detail="Administrator access required")
    store = get_user_store()
    return UserListResponse(users=store.list_users() if store else [])


@app.get("/api/auth/verify", response_model=AuthStatusResponse)
async def verify_auth(request: Request):
    """Check if the current session is valid."""
    auth_required = _auth_required()

    if not auth_required:
        return AuthStatusResponse(
            authenticated=True, username="admin", auth_required=False, is_admin=True
        )

    token = _extract_token(request)
    if token:
        username = verify_jwt(token, config.auth.jwt_secret)
        if username:
            return AuthStatusResponse(
                authenticated=True,
                username=username,
                auth_required=True,
                is_admin=_is_admin(username),
            )

    return AuthStatusResponse(authenticated=False, auth_required=True)


# --- Protected Endpoints ---

@app.get("/config/providers")
async def get_providers(_user: str = Depends(get_current_user)):
    """Get available LLM providers"""
    providers = []
    if config.llm.google_api_key:
        providers.append({
            "id": "gemini",
            "name": "Google Gemini",
            "model": config.llm.gemini_model,
            "models": PROVIDER_MODELS["gemini"]
        })
    if config.llm.openai_api_key:
        providers.append({
            "id": "openai",
            "name": "OpenAI",
            "model": config.llm.openai_model,
            "models": PROVIDER_MODELS["openai"]
        })
    if config.llm.anthropic_api_key:
        providers.append({
            "id": "claude",
            "name": "Anthropic Claude",
            "model": config.llm.anthropic_model,
            "models": PROVIDER_MODELS["claude"]
        })
    if config.llm.zai_api_key:
        providers.append({
            "id": "zhipu",
            "name": "Z.AI GLM",
            "model": config.llm.zai_model,
            "models": PROVIDER_MODELS["zhipu"]
        })
    if config.llm.muse_api_key:
        providers.append({
            "id": "muse",
            "name": "Meta Muse",
            "model": config.llm.muse_model,
            "models": PROVIDER_MODELS["muse"]
        })
    if config.llm.openrouter_api_key:
        providers.append({
            "id": "openrouter",
            "name": "OpenRouter",
            "model": config.llm.openrouter_model,
            "models": PROVIDER_MODELS["openrouter"]
        })
    return {
        "providers": providers,
        "account_id": config.aws.account_id,
        "current_provider": config.llm.provider
    }


@app.post("/api/generate-policy", response_model=PolicyResponseModel)
async def generate_policy(request: PolicyRequest, user: str = Depends(get_current_user)):
    """
    Generate IAM policy from natural language request

    Uses configured LLM provider to generate least-privilege IAM policy.
    Returns policy with risk assessment and approval requirements.
    """
    try:
        # Saved profiles override provider/model/key; otherwise body/env apply.
        provider_id, model, api_key, _ = _resolve_evaluation_config(
            user, request.provider, request.model, request.profile_id
        )
        provider = get_llm_provider(provider_id, model, api_key)

        # Generate policy
        response: PolicyResponse = provider.generate_policy(request.request_text)

        # Calculate max duration based on risk
        max_duration = get_max_duration(response.risk)
        actual_duration = min(request.duration, max_duration)

        # Determine if auto-approved
        auto_approved = response.risk.lower() == "low"

        return PolicyResponseModel(
            policy=response.policy,
            risk=response.risk,
            explanation=response.explanation,
            approver_note=response.approver_note,
            auto_approved=auto_approved,
            max_duration=actual_duration
        )

    except UserFacingError as e:
        # Log the full error but return user-friendly message
        logger.error(f"Policy generation failed (user-facing): {e.log_message}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.user_message
        )
    except Exception as e:
        logger.error(f"Policy generation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred. Please try again."
        )


@app.post("/api/issue-credentials", response_model=CredentialsResponse)
async def issue_credentials(request: IssueCredentialsRequest, _user: str = Depends(get_current_user)):
    """
    Issue temporary AWS credentials via STS AssumeRole

    Requires policy to be approved (manually or auto-approved for low risk).

    A caller-asserted `approved` flag alone is not enough: overly broad
    policies are rejected before STS is ever called.
    """
    if request.approved is not True:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Policy must be approved before credentials can be issued.",
        )
    violation = find_overly_broad_policy_violation(request.policy)
    if violation is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=violation,
        )
    try:
        # Generate credentials
        creds = sts_service.assume_role_with_policy(request.policy, request.duration)

        # Send notification with the reviewed assessment. Normalize unknown
        # risk labels to "medium" so the channel formatting never breaks.
        risk = request.risk.lower()
        if risk not in ("low", "medium", "high", "critical"):
            risk = "medium"
        send_audit_notification(
            auto_approved=request.auto_approved,
            req="Policy-based credential issuance",
            risk=risk,
            duration=request.duration,
            approver=request.approver
        )

        return CredentialsResponse(
            access_key_id=creds['AccessKeyId'],
            secret_access_key=creds['SecretAccessKey'],
            session_token=creds['SessionToken'],
            expiration=creds['Expiration'].isoformat(),
            region="us-east-1"
        )

    except STSAssumeRoleError as e:
        logger.error(f"STS AssumeRole failed: {e}")
        # Create a user-friendly error for AWS STS issues
        account_id = config.aws.account_id or "YOUR_ACCOUNT_ID"
        role_name = config.aws.role_arn.split("/")[-1] if config.aws.role_arn else "YOUR_ROLE_NAME"
        error_detail = f"""🔑 **AWS Credential Issue**

Unable to issue temporary credentials. This could be due to:

• **Invalid AWS credentials** - Check `AWS_ACCOUNT_ID` and `AWS_ROLE_NAME` in your `.env`
• **Role doesn't exist** - Ensure the IAM role exists in your AWS account
• **Permission denied** - The role trust policy may not allow your account to assume it

**To fix:**
1. Verify the IAM role exists: `arn:aws:iam::{account_id}:role/{role_name}`
2. Check the trust relationship allows your AWS account
3. Ensure your AWS credentials have `sts:AssumeRole` permission"""
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=error_detail
        )
    except Exception as e:
        logger.error(f"Credential issuance failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to issue credentials. Please try again."
        )


class RejectionGuidanceRequest(BaseModel):
    """Request model for rejection guidance"""
    original_request: str = Field(..., description="The original request text")
    policy: dict = Field(..., description="The generated policy that was rejected")
    risk: str = Field(..., description="Risk level of the policy")
    provider: str = Field(default="gemini", description="LLM provider to use")
    model: Optional[str] = Field(default=None, description="Model to use (overrides provider default)")


class RejectionGuidanceResponse(BaseModel):
    """Response model for rejection guidance"""
    guidance: str


@app.post("/api/generate-rejection-guidance", response_model=RejectionGuidanceResponse)
async def generate_rejection_guidance(request: RejectionGuidanceRequest, _user: str = Depends(get_current_user)):
    """
    Generate AI guidance for rejected requests to help user resubmit with better scoping

    Provides specific suggestions based on the original request, generated policy, and risk level.
    """
    try:
        # Rejection guidance uses the fast tier unless the caller pins a model
        model = request.model or fast_model_for(request.provider)
        provider = get_llm_provider(request.provider, model)

        # Generate guidance
        guidance = provider.generate_rejection_guidance(
            request.original_request,
            request.policy,
            request.risk
        )

        return RejectionGuidanceResponse(guidance=guidance)

    except UserFacingError as e:
        # Log the full error but return user-friendly message
        logger.error(f"Rejection guidance generation failed (user-facing): {e.log_message}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.user_message
        )
    except Exception as e:
        logger.error(f"Rejection guidance generation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to generate guidance. Please review your request and try again."
        )


# --- Access Request + Review Workflow ---
#
# Requests (what a user asked for + the evaluated LLM response) are
# persisted separately from approvals (what a reviewer decided). Low-risk
# requests are marked approved automatically but issue NO credentials
# until the requester activates them when ready.

def _resolve_evaluation_config(
    user: str,
    body_provider: Optional[str],
    body_model: Optional[str],
    profile_id: Optional[int],
) -> tuple[Optional[str], Optional[str], Optional[str], str]:
    """Resolve provider/model/key for an evaluation.

    A profile id selects the user's own stored profile (decrypted
    in-process, never logged); otherwise the request body (or server env)
    applies. Returns (provider, model, api_key, audit_label).
    """
    if profile_id is None:
        return body_provider, body_model, None, "server-default"
    store = _require_profile_store()
    try:
        creds = store.get_credentials(user, profile_id)
    except ProfileStoreError as e:
        code = 404 if e.code == "not_found" else 400
        raise HTTPException(status_code=code, detail=str(e))
    if not store.is_enabled(creds["provider"], creds["model"]):
        raise HTTPException(
            status_code=400,
            detail=f"{creds['provider']}/{creds['model']} is not enabled. Ask an administrator.",
        )
    public = store.get_profile_public(user, profile_id)
    label = f"profile:{public['name']}" if public else f"profile:{profile_id}"
    return creds["provider"], creds["model"], creds["api_key"], label


def _evaluate_access_request(
    provider_id: Optional[str],
    model: Optional[str],
    request_text: str,
    duration: int,
    api_key: Optional[str] = None,
):
    """Run the LLM evaluation shared by submit and resubmit.

    Returns (PolicyResponse, clamped duration, auto_approved).
    """
    provider = get_llm_provider(provider_id, model, api_key)
    response: PolicyResponse = provider.generate_policy(request_text)
    max_duration = get_max_duration(response.risk)
    actual_duration = min(duration, max_duration)
    auto_approved = response.risk.lower() == "low"
    return response, actual_duration, auto_approved


def _get_stored_request(request_id: int) -> dict:
    store = _require_request_store()
    stored = store.get(request_id)
    if stored is None:
        raise HTTPException(status_code=404, detail=f"Request {request_id} not found.")
    return stored


def _require_owner_or_admin(stored: dict, user: str) -> None:
    if stored["requester"] != user and not _is_admin(user):
        raise HTTPException(
            status_code=403, detail="You can only view your own requests."
        )


@app.post("/api/requests", response_model=AccessRequestModel, status_code=201)
async def submit_access_request(
    body: SubmitAccessRequest, user: str = Depends(get_current_user)
):
    """Evaluate a request with the LLM, persist it, and route for review.

    Low-risk requests are marked approved (actor "system" in the audit
    trail) but still require POST /api/requests/{id}/activate before any
    credentials exist. Everything else waits in pending_review.
    """
    provider_id, model, api_key, profile_label = _resolve_evaluation_config(
        user, body.provider, body.model, body.profile_id
    )
    try:
        response, actual_duration, auto_approved = _evaluate_access_request(
            provider_id, model, body.request_text, body.duration, api_key
        )
    except UserFacingError as e:
        logger.error(f"Access request evaluation failed (user-facing): {e.log_message}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.user_message)
    except Exception:
        logger.error("Access request evaluation failed", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred. Please try again.",
        )

    request_status = STATUS_APPROVED if auto_approved else STATUS_PENDING
    store = _require_request_store()
    try:
        stored = store.create(
            requester=user,
            request_text=body.request_text,
            provider=provider_id or "gemini",
            model=model,
            duration=actual_duration,
            policy=response.policy,
            risk=response.risk,
            explanation=response.explanation,
            approver_note=response.approver_note,
            auto_approved=auto_approved,
            status=request_status,
        )
    except RequestStoreError as e:
        raise HTTPException(status_code=400, detail=str(e))

    _audit(
        "submitted",
        request_id=stored["id"],
        actor=user,
        to_status=request_status,
        risk=response.risk,
        provider=stored["provider"],
        profile=profile_label,
        duration_hours=actual_duration,
        revision=stored["revision"],
    )
    if auto_approved:
        _audit(
            "auto_approved",
            request_id=stored["id"],
            actor="system",
            actor_role="automated",
            to_status=request_status,
            risk=response.risk,
        )
    else:
        _audit(
            "queued_for_review",
            request_id=stored["id"],
            actor="system",
            actor_role="automated",
            to_status=request_status,
            risk=response.risk,
        )
    return stored


class RecordAccessRequest(BaseModel):
    """Persist an already-evaluated request without re-running the LLM.

    Used by the desktop shell: its Agent_Kit evaluates through this same
    backend's /api/generate-policy seconds earlier, so re-running the model
    would double LLM spend for an identical result. Trust is equivalent to
    /api/requests — the policy is re-checked by the server guardrail, the
    risk label is normalized (never trusted blindly), and the duration is
    clamped to the risk ceiling.
    """
    request_text: str = Field(..., min_length=10)
    provider: Optional[str] = Field(default="gemini")
    model: Optional[str] = Field(default=None)
    duration: int = Field(default=2, ge=1, le=12)
    policy: dict
    risk: str = Field(default="medium")
    explanation: str = Field(default="")
    approver_note: str = Field(default="")
    profile_id: Optional[int] = Field(default=None, description="Your saved profile (provider/model attribution only; no LLM call)")


@app.post("/api/requests/record", response_model=AccessRequestModel, status_code=201)
async def record_access_request(
    body: RecordAccessRequest, user: str = Depends(get_current_user)
):
    """Store a freshly evaluated policy as a review-routed request."""
    violation = find_overly_broad_policy_violation(body.policy)
    if violation is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=violation)
    provider_id, model, _, profile_label = _resolve_evaluation_config(
        user, body.provider, body.model, body.profile_id
    )
    risk = (body.risk or "").strip().lower()
    if risk not in ("low", "medium", "high", "critical"):
        risk = "medium"
    actual_duration = min(body.duration, get_max_duration(risk))
    auto_approved = risk == "low"
    request_status = STATUS_APPROVED if auto_approved else STATUS_PENDING
    store = _require_request_store()
    try:
        stored = store.create(
            requester=user,
            request_text=body.request_text,
            provider=provider_id or "gemini",
            model=model,
            duration=actual_duration,
            policy=body.policy,
            risk=risk,
            explanation=body.explanation,
            approver_note=body.approver_note,
            auto_approved=auto_approved,
            status=request_status,
        )
    except RequestStoreError as e:
        raise HTTPException(status_code=400, detail=str(e))
    _audit(
        "submitted",
        request_id=stored["id"],
        actor=user,
        to_status=request_status,
        risk=risk,
        provider=stored["provider"],
        profile=profile_label,
        duration_hours=actual_duration,
        revision=stored["revision"],
    )
    _audit(
        "auto_approved" if auto_approved else "queued_for_review",
        request_id=stored["id"],
        actor="system",
        actor_role="automated",
        to_status=request_status,
        risk=risk,
    )
    return stored


@app.get("/api/requests", response_model=list[AccessRequestModel])
async def list_access_requests(
    status: Optional[str] = None,
    mine: bool = False,
    user: str = Depends(get_current_user),
):
    """List requests — your own, or all when you are an admin.

    Admins pass mine=true for the "my requests" view; regular users always
    see only their own rows regardless of flags.
    """
    store = _require_request_store()
    try:
        if _is_admin(user) and not mine:
            return store.list(status=status)
        return store.list(requester=user, status=status)
    except RequestStoreError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/requests/{request_id}", response_model=AccessRequestModel)
async def get_access_request(request_id: int, user: str = Depends(get_current_user)):
    """Request detail: original text plus the evaluated LLM response."""
    stored = _get_stored_request(request_id)
    _require_owner_or_admin(stored, user)
    return stored


@app.post("/api/requests/{request_id}/review", response_model=AccessRequestModel)
async def review_access_request(
    request_id: int, body: ReviewAccessRequest, user: str = Depends(get_current_user)
):
    """Approve, deny, or send back a pending request (administrators only)."""
    if not _is_admin(user):
        raise HTTPException(status_code=403, detail="Administrator access required")
    decisions = {
        "approve": ("approved", "approved"),
        "deny": ("denied", "denied"),
        "changes_requested": ("changes_requested", "changes_requested"),
    }
    if body.decision not in decisions:
        raise HTTPException(
            status_code=400,
            detail="Decision must be one of: approve, deny, changes_requested.",
        )
    if body.decision in ("deny", "changes_requested") and not (body.feedback or "").strip():
        raise HTTPException(
            status_code=400,
            detail="Feedback is required when denying or sending a request back.",
        )
    stored = _get_stored_request(request_id)
    if stored["status"] != STATUS_PENDING:
        raise HTTPException(
            status_code=400,
            detail=f"Only pending requests can be reviewed (request {request_id} is {stored['status']}).",
        )
    store = _require_request_store()
    try:
        event, to_status = decisions[body.decision]
        updated = store.set_status(
            request_id, to_status, reviewer=user, feedback=(body.feedback or None)
        )
    except RequestStoreError as e:
        code = 404 if e.code == "not_found" else 400
        raise HTTPException(status_code=code, detail=str(e))
    _audit(
        event,
        request_id=request_id,
        actor=user,
        from_status=stored["status"],
        to_status=to_status,
        risk=stored["risk"],
        feedback=body.feedback,
    )
    return updated


@app.post("/api/requests/{request_id}/resubmit", response_model=AccessRequestModel)
async def resubmit_access_request(
    request_id: int, body: ResubmitAccessRequest, user: str = Depends(get_current_user)
):
    """Re-evaluate a sent-back request as a new revision (owner only)."""
    stored = _get_stored_request(request_id)
    if stored["requester"] != user:
        raise HTTPException(
            status_code=403, detail="Only the requester can resubmit this request."
        )
    request_text = body.request_text or stored["request_text"]
    duration = body.duration if body.duration is not None else stored["duration"]
    provider_id, model, api_key, profile_label = _resolve_evaluation_config(
        user, body.provider or stored["provider"], body.model, body.profile_id
    )
    try:
        response, actual_duration, auto_approved = _evaluate_access_request(
            provider_id, model, request_text, duration, api_key
        )
    except UserFacingError as e:
        logger.error(f"Access request re-evaluation failed (user-facing): {e.log_message}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.user_message)
    except Exception:
        logger.error("Access request re-evaluation failed", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred. Please try again.",
        )
    request_status = STATUS_APPROVED if auto_approved else STATUS_PENDING
    store = _require_request_store()
    try:
        updated = store.resubmit(
            request_id,
            request_text=request_text,
            provider=provider_id or "gemini",
            model=model,
            duration=actual_duration,
            policy=response.policy,
            risk=response.risk,
            explanation=response.explanation,
            approver_note=response.approver_note,
            auto_approved=auto_approved,
            status=request_status,
        )
    except RequestStoreError as e:
        code = 404 if e.code == "not_found" else 400
        raise HTTPException(status_code=code, detail=str(e))
    _audit(
        "resubmitted",
        request_id=request_id,
        actor=user,
        from_status=stored["status"],
        to_status=request_status,
        risk=response.risk,
        profile=profile_label,
        revision=updated["revision"],
    )
    return updated


@app.post("/api/requests/{request_id}/discard", response_model=AccessRequestModel)
async def discard_access_request(
    request_id: int, user: str = Depends(get_current_user)
):
    """Withdraw an open request (owner, or any admin)."""
    stored = _get_stored_request(request_id)
    if stored["requester"] != user and not _is_admin(user):
        raise HTTPException(
            status_code=403, detail="Only the requester or an administrator can discard this request."
        )
    store = _require_request_store()
    try:
        updated = store.set_status(request_id, "discarded", reviewer=user)
    except RequestStoreError as e:
        code = 404 if e.code == "not_found" else 400
        raise HTTPException(status_code=code, detail=str(e))
    _audit(
        "discarded",
        request_id=request_id,
        actor=user,
        from_status=stored["status"],
        to_status="discarded",
    )
    return updated


@app.post("/api/requests/{request_id}/activate", response_model=CredentialsResponse)
async def activate_access_request(
    request_id: int, user: str = Depends(get_current_user)
):
    """Issue STS credentials for an approved request, when the requester is ready.

    Approval alone creates no credentials — not even for auto-approved
    low-risk requests. The owner calls this when they are ready to use the
    access; the stored (reviewed) policy is re-checked by the server
    guardrail before STS is ever called.
    """
    stored = _get_stored_request(request_id)
    if stored["requester"] != user:
        raise HTTPException(
            status_code=403, detail="Only the requester can activate this request."
        )
    if stored["status"] != STATUS_APPROVED:
        raise HTTPException(
            status_code=400,
            detail=f"Only approved requests can be activated (request {request_id} is {stored['status']}).",
        )
    violation = find_overly_broad_policy_violation(stored["policy"])
    if violation is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=violation)
    base_role_arn, base_role_class = _select_base_role(stored["policy"])
    try:
        creds = sts_service.assume_role_with_policy(
            stored["policy"], stored["duration"], role_arn=base_role_arn
        )
    except STSAssumeRoleError as e:
        logger.error(f"STS AssumeRole failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to issue credentials. Please try again.",
        )
    except Exception:
        logger.error("Credential activation failed", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to issue credentials. Please try again.",
        )
    expiration = creds["Expiration"].isoformat()
    store = _require_request_store()
    try:
        store.mark_activated(request_id, credentials_expires_at=expiration)
    except RequestStoreError as e:
        # Credentials were already issued; the activation record failed.
        # Surface loudly instead of letting the request be activated twice.
        logger.error("Activation record failed for request %s: %s", request_id, e)
        raise HTTPException(status_code=500, detail="Credentials issued but activation was not recorded. Contact an administrator.")
    reviewer = stored["reviewer"] or "system (auto-approved)"
    _audit(
        "activated",
        request_id=request_id,
        actor=user,
        from_status=STATUS_APPROVED,
        to_status="activated",
        risk=stored["risk"],
        reviewer=reviewer,
        base_role=base_role_class,
        duration_hours=stored["duration"],
    )
    risk = stored["risk"].lower()
    if risk not in ("low", "medium", "high", "critical"):
        risk = "medium"
    send_audit_notification(
        auto_approved=stored["auto_approved"],
        req=stored["request_text"],
        risk=risk,
        duration=stored["duration"],
        approver=reviewer,
    )
    return CredentialsResponse(
        access_key_id=creds["AccessKeyId"],
        secret_access_key=creds["SecretAccessKey"],
        session_token=creds["SessionToken"],
        expiration=expiration,
        region="us-east-1",
    )


@app.get("/api/audit", response_model=list[AuditEventModel])
async def read_audit_trail(
    request_id: Optional[int] = None,
    actor: Optional[str] = None,
    event: Optional[str] = None,
    limit: int = 100,
    user: str = Depends(get_current_user),
):
    """Browse the JSONL audit trail (administrators only)."""
    if not _is_admin(user):
        raise HTTPException(status_code=403, detail="Administrator access required")
    log = get_audit_log()
    if log is None:
        raise HTTPException(status_code=500, detail="Audit log is unavailable")
    return log.read(
        limit=min(max(limit, 1), 500),
        request_id=request_id,
        actor=actor,
        event=event,
    )


# --- LLM Profiles + Provider Catalog ---
#
# Users own named profiles (provider + model + their own API key,
# encrypted at rest). Key material is never logged, never audited, and
# never serialized — read APIs expose has_key + a last-4 hint only.


def _profile_error_to_http(e: ProfileStoreError) -> HTTPException:
    code = 404 if e.code in ("not_found", "unknown_model") else 400
    if e.code == "name_taken":
        code = 409
    return HTTPException(status_code=code, detail=str(e))


@app.get("/api/providers/catalog", response_model=list[CatalogEntryModel])
async def list_provider_catalog(user: str = Depends(get_current_user)):
    """Provider/model pairs the administrator has made available."""
    return _require_profile_store().list_catalog()


@app.put("/api/providers/catalog", response_model=CatalogEntryModel)
async def update_provider_catalog(
    body: CatalogUpdateBody, user: str = Depends(get_current_user)
):
    """Enable or disable a provider/model pair (administrators only)."""
    if not _is_admin(user):
        raise HTTPException(status_code=403, detail="Administrator access required")
    try:
        return _require_profile_store().set_catalog_enabled(
            body.provider, body.model, body.enabled
        )
    except ProfileStoreError as e:
        raise _profile_error_to_http(e)


@app.get("/api/profiles", response_model=list[ProfileModel])
async def list_profiles(user: str = Depends(get_current_user)):
    """Your saved LLM profiles (keys never included)."""
    return _require_profile_store().list_profiles(user)


@app.post("/api/profiles", response_model=ProfileModel, status_code=201)
async def create_profile(body: ProfileCreateBody, user: str = Depends(get_current_user)):
    """Save a named profile with your own provider key."""
    try:
        return _require_profile_store().create_profile(
            username=user,
            name=body.name,
            provider=body.provider,
            model=body.model,
            api_key=body.api_key,
        )
    except ProfileStoreError as e:
        raise _profile_error_to_http(e)


@app.patch("/api/profiles/{profile_id}", response_model=ProfileModel)
async def update_profile(
    profile_id: int, body: ProfileUpdateBody, user: str = Depends(get_current_user)
):
    """Rename a profile and/or replace its key."""
    try:
        return _require_profile_store().update_profile(
            user, profile_id, name=body.name, api_key=body.api_key
        )
    except ProfileStoreError as e:
        raise _profile_error_to_http(e)


@app.delete("/api/profiles/{profile_id}", status_code=204)
async def delete_profile(profile_id: int, user: str = Depends(get_current_user)):
    """Delete one of your profiles."""
    try:
        _require_profile_store().delete_profile(user, profile_id)
    except ProfileStoreError as e:
        raise _profile_error_to_http(e)
    return None


@app.post("/api/profiles/{profile_id}/activate", response_model=ProfileModel)
async def activate_profile(profile_id: int, user: str = Depends(get_current_user)):
    """Make a profile your default for new evaluations."""
    try:
        return _require_profile_store().set_active(user, profile_id)
    except ProfileStoreError as e:
        raise _profile_error_to_http(e)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "IAM-Dynamic API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
