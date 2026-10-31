"""
Shared test setup.

config.py builds its singleton at import time, so required environment
variables must exist before any backend module is imported. Tests run from
the backend/ directory (as CI does), but on a developer machine the repo
root .env is picked up by load_dotenv — provider keys from it are stripped
per test so the suite is hermetic and never fires real API calls.
"""
import os
import tempfile

import pytest

# Required by AWSConfig (Field(...)) — dummy value, never used against AWS
os.environ.setdefault("AWS_ACCOUNT_ID", "123456789012")
os.environ.setdefault("AWS_ROLE_NAME", "TestSessionRole")

# main.get_user_store() lazily opens config.auth.users_db_path (default
# backend/users.db). A developer's local registrations would then enable auth
# mid-suite and break tests that assume the auth bypass — so point the default
# at a throwaway file BEFORE any backend module is imported. main's
# load_dotenv() never overrides an already-set variable, and the per-test
# fixture below narrows this further to a fresh empty DB per test.
os.environ.setdefault(
    "AUTH_USERS_DB", os.path.join(tempfile.mkdtemp(prefix="iam-test-"), "users.db")
)

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
def _isolated_user_store(tmp_path, monkeypatch):
    """Give every test a fresh empty users DB instead of backend/users.db.

    main.user_store is a lazily-created singleton, so without this a store
    built by one test (or a developer's real users.db) leaks into the next
    and flips _auth_required(). Each test starts with user_store=None and
    users_db_path pointing at its own tmp dir; the store built during the
    test is closed afterwards. Tests that install their own store (e.g.
    test_auth_users' `store` fixture) override this via monkeypatch and
    close it in their own teardown — closing twice here is safe.
    """
    import main

    existing = main.user_store
    if existing is not None:
        try:
            existing.close()
        except Exception:
            pass
    monkeypatch.setattr(main, "user_store", None)
    monkeypatch.setattr(main.config.auth, "users_db_path", str(tmp_path / "users.db"))
    yield
    store = main.user_store
    if store is not None:
        try:
            store.close()
        except Exception:
            pass


@pytest.fixture(autouse=True)
def _isolated_request_store(tmp_path, monkeypatch):
    """Give every test a fresh requests DB and JSONL audit log.

    Mirrors _isolated_user_store: main.request_store/main.audit_log are
    lazily-created singletons, so reset them per test and point the paths
    at tmp dirs. A developer's real requests.db and audit.jsonl are never
    touched by the suite.
    """
    import main

    for attr in ("request_store", "audit_log"):
        existing = getattr(main, attr)
        if existing is not None:
            try:
                existing.close()
            except Exception:
                pass
        monkeypatch.setattr(main, attr, None)
    monkeypatch.setattr(
        main.config, "requests_db_path", str(tmp_path / "requests.db")
    )
    monkeypatch.setattr(
        main.config, "audit_log_path", str(tmp_path / "audit.jsonl")
    )
    yield
    for attr in ("request_store", "audit_log"):
        store = getattr(main, attr)
        if store is not None:
            try:
                store.close()
            except Exception:
                pass


@pytest.fixture(autouse=True)
def _isolated_profile_store(tmp_path, monkeypatch):
    """Give every test a fresh profiles DB + deterministic encryption secret.

    Mirrors _isolated_user_store: main.profile_store is a lazily-created
    singleton, so reset it per test and point the path at a tmp dir. The
    secret is fixed so Fernet round-trips are deterministic and never touch
    a developer's real profiles.db.
    """
    import main

    existing = getattr(main, "profile_store", None)
    if existing is not None:
        try:
            existing.close()
        except Exception:
            pass
    monkeypatch.setattr(main, "profile_store", None)
    monkeypatch.setattr(main.config, "profiles_db_path", str(tmp_path / "profiles.db"))
    monkeypatch.setattr(main.config, "profile_encryption_key", "test-encryption-secret")
    yield
    store = main.profile_store
    if store is not None:
        try:
            store.close()
        except Exception:
            pass


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
