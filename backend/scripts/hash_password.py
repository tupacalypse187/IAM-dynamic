#!/usr/bin/env python3
"""Generate a bcrypt hash for use in AUTH_PASSWORD_HASH env var."""
import getpass
import bcrypt

password = getpass.getpass("Enter password: ")
confirm = getpass.getpass("Confirm password: ")

if password != confirm:
    print("Error: passwords do not match")
    raise SystemExit(1)

hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
print(f"\nAUTH_PASSWORD_HASH={hashed.decode('utf-8')}")
