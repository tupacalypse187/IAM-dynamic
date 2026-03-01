#!/usr/bin/env python3
"""Generate a bcrypt hash for use in AUTH_PASSWORD_HASH env var."""
import getpass
from passlib.hash import bcrypt

password = getpass.getpass("Enter password: ")
confirm = getpass.getpass("Confirm password: ")

if password != confirm:
    print("Error: passwords do not match")
    raise SystemExit(1)

print(f"\nAUTH_PASSWORD_HASH={bcrypt.hash(password)}")
