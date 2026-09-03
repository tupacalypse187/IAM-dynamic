"""
Shared test setup.

config.py builds its singleton at import time, so required environment
variables must exist before any backend module is imported. Tests run from
the backend/ directory (as CI does), but on a developer machine the repo
root .env is picked up by load_dotenv — provider keys from it are stripped
per test so the suite is hermetic and never fires real API calls.
"""
import os

import pytest

# Required by AWSConfig (Field(...)) — dummy value, never used against AWS
os.environ.setdefault("AWS_ACCOUNT_ID", "123456789012")
os.environ.setdefault("AWS_ROLE_NAME", "TestSessionRole")

PROVIDER_KEY_VARS = [
    "GOOGLE_API_KEY",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "ZAI_API_KEY",
    "MUSE_API_KEY",
    "OPENROUTER_API_KEY",
]

# The API tests hit endpoints protected by Depends(get_current_user); auth is
# only bypassed when no password hash is configured, so force auth off for a
# deterministic result even if a developer's .env enables it.
AUTH_VARS = ["AUTH_PASSWORD_HASH", "JWT_SECRET"]


@pytest.fixture(autouse=True)
def _hermetic_provider_keys(monkeypatch):
    """Remove real provider credentials and auth config for every test.

    Providers read os.getenv at construction time (not import time), and a
    developer's .env may have been loaded into the environment by
    load_dotenv() during module import — strip it per test so missing-key
    behavior stays deterministic and endpoints stay auth-bypassed.
    """
    for key in PROVIDER_KEY_VARS + AUTH_VARS:
        monkeypatch.delenv(key, raising=False)
