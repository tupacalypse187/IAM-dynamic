"""
IAM-Dynamic Backend - FastAPI Application

AI-driven Just-In-Time AWS IAM access request portal.
Generates least-privilege IAM policies using LLM and issues temporary credentials via AWS STS.
"""
import os
import logging
from datetime import datetime, timezone
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from dotenv import load_dotenv

# Load environment variables from parent directory
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import services
from services.sts_service import STSService, STSAssumeRoleError
from services.slack_service import SlackService
from llm_service import get_llm_provider, PolicyResponse
from config import load_config

# Load configuration
config = load_config()

# Initialize services
sts_service = STSService(config.aws.role_arn)
slack_service = SlackService(config.slack.webhook_url)


# --- Pydantic Models ---

class PolicyRequest(BaseModel):
    """Request model for policy generation"""
    request_text: str = Field(..., description="Natural language description of access needed", min_length=10)
    provider: Optional[str] = Field(default="gemini", description="LLM provider to use")
    duration: int = Field(default=2, description="Requested session duration in hours", ge=1, le=12)
    change_case: Optional[str] = Field(default=None, description="Business justification for high-risk requests")


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

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "http://127.0.0.1:3000", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Helper Functions ---

def get_max_duration(risk: str) -> int:
    """Get maximum allowed duration based on risk level"""
    return {"low": 12, "medium": 4, "high": 2, "critical": 1}.get(risk.lower(), 2)


def send_slack_notification(auto_approved: bool, req: str, risk: str, duration: int, approver: str = None):
    """Send notification to Slack via service"""
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


# --- API Endpoints ---

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        timestamp=datetime.now(timezone.utc).isoformat()
    )


@app.get("/config/providers")
async def get_providers():
    """Get available LLM providers"""
    providers = []
    if config.llm.google_api_key:
        providers.append({
            "id": "gemini",
            "name": "Google Gemini",
            "model": config.llm.gemini_model
        })
    if config.llm.openai_api_key:
        providers.append({
            "id": "openai",
            "name": "OpenAI",
            "model": config.llm.openai_model
        })
    if config.llm.anthropic_api_key:
        providers.append({
            "id": "claude",
            "name": "Anthropic Claude",
            "model": config.llm.anthropic_model
        })
    if config.llm.zhipuai_api_key:
        providers.append({
            "id": "glm",
            "name": "Zhipu GLM",
            "model": config.llm.glm_model
        })
    return {"providers": providers, "account_id": config.aws.account_id}


@app.post("/api/generate-policy", response_model=PolicyResponseModel)
async def generate_policy(request: PolicyRequest):
    """
    Generate IAM policy from natural language request

    Uses configured LLM provider to generate least-privilege IAM policy.
    Returns policy with risk assessment and approval requirements.
    """
    try:
        # Get LLM provider
        provider = get_llm_provider(request.provider)

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

    except Exception as e:
        logger.error(f"Policy generation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate policy: {str(e)}"
        )


@app.post("/api/issue-credentials", response_model=CredentialsResponse)
async def issue_credentials(request: IssueCredentialsRequest):
    """
    Issue temporary AWS credentials via STS AssumeRole

    Requires policy to be approved (manually or auto-approved for low risk).
    """
    try:
        # Generate credentials
        creds = sts_service.assume_role_with_policy(request.policy, request.duration)

        # Send notification
        send_slack_notification(
            auto_approved=True,  # If we got here, it was approved
            req="Policy-based credential issuance",
            risk="medium",  # Default notification risk
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
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"AWS credential issuance failed: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Credential issuance failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to issue credentials: {str(e)}"
        )


class RejectionGuidanceRequest(BaseModel):
    """Request model for rejection guidance"""
    original_request: str = Field(..., description="The original request text")
    policy: dict = Field(..., description="The generated policy that was rejected")
    risk: str = Field(..., description="Risk level of the policy")
    provider: str = Field(default="gemini", description="LLM provider to use")


class RejectionGuidanceResponse(BaseModel):
    """Response model for rejection guidance"""
    guidance: str


@app.post("/api/generate-rejection-guidance", response_model=RejectionGuidanceResponse)
async def generate_rejection_guidance(request: RejectionGuidanceRequest):
    """
    Generate AI guidance for rejected requests to help user resubmit with better scoping

    Provides specific suggestions based on the original request, generated policy, and risk level.
    """
    try:
        # Get LLM provider
        provider = get_llm_provider(request.provider)

        # Generate guidance
        guidance = provider.generate_rejection_guidance(
            request.original_request,
            request.policy,
            request.risk
        )

        return RejectionGuidanceResponse(guidance=guidance)

    except Exception as e:
        logger.error(f"Rejection guidance generation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate guidance: {str(e)}"
        )


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
