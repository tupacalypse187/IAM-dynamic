#!/usr/bin/env python3
"""Seed throwaway demo requester accounts for the hackathon view-as demo.

Creates alice, bob, and carol (matching the default DEMO_VIEW_USERS
allowlist) with random one-time passwords printed to stdout. The admin
never needs these passwords — view-as uses short-lived impersonation
tokens — but they let a presenter log in as each user directly too.

TEMPORARY hackathon aid: do not run against production data, rotate or
delete the accounts afterwards, and remove this file with the
impersonate endpoint.

Usage:
    python backend/scripts/seed_demo_users.py [--db PATH] [--users alice,bob,carol]
"""
import argparse
import secrets
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from services.user_store import UserStore  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(BACKEND_DIR / "users.db"))
    parser.add_argument("--users", default="alice,bob,carol")
    args = parser.parse_args()

    usernames = [u.strip() for u in args.users.split(",") if u.strip()]
    if not usernames:
        print("No usernames given.", file=sys.stderr)
        return 1

    store = UserStore(args.db)
    try:
        existing = {u["username"] for u in store.list_users()}
        clash = [u for u in usernames if u in existing]
        if clash:
            print(
                f"Refusing to seed — already registered: {', '.join(clash)}. "
                "Delete them first if you really want fresh demo accounts.",
                file=sys.stderr,
            )
            return 1
        print("Seeded demo accounts (log in directly, or admin view-as):")
        for username in usernames:
            password = secrets.token_urlsafe(12)
            store.register(username, password)
            print(f"  {username} / {password}")
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
