"""
Cloudflare Turnstile verification service.

When no secret key is configured, verification is skipped (dev mode).
"""
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


class TurnstileService:
    def __init__(self, secret_key: Optional[str] = None):
        self.secret_key = secret_key

    @property
    def enabled(self) -> bool:
        return bool(self.secret_key)

    async def verify(self, token: Optional[str], remote_ip: Optional[str] = None) -> bool:
        """Verify a Turnstile token. Returns True if Turnstile is not configured."""
        if not self.secret_key:
            return True

        if not token:
            logger.warning("Turnstile token missing but verification is enabled")
            return False

        payload = {
            "secret": self.secret_key,
            "response": token,
        }
        if remote_ip:
            payload["remoteip"] = remote_ip

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(VERIFY_URL, data=payload)
                result = resp.json()
                success = result.get("success", False)
                if not success:
                    logger.warning(f"Turnstile verification failed: {result.get('error-codes', [])}")
                return success
        except Exception as e:
            logger.error(f"Turnstile verification error: {e}")
            return False
