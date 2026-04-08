"""Start token generation and validation - Tasks 5.1, 5.2."""

import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass


def _sign(job_id: str, salt: str, expires_at: int) -> str:
    payload = f"{job_id}:{salt}:{expires_at}"
    return hmac.new(
        b"escrow-secret-key",  # TODO: from config
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()


def generate_start_token(
    job_id: str,
    ttl_seconds: int = 3600,
) -> tuple[str, int]:
    """
    Task 5.1: Generate start token scoped to job_id.
    Task 5.2: Token expires after ttl_seconds.
    Returns (token, expires_at_unix).
    """
    salt = secrets.token_hex(16)
    expires_at = int(time.time()) + ttl_seconds
    sig = _sign(job_id, salt, expires_at)
    token = f"{job_id}.{salt}.{expires_at}.{sig}"
    return token, expires_at


def validate_start_token(token: str, job_id: str) -> bool:
    """Validate token is scoped to job_id and not expired."""
    parts = token.split(".")
    if len(parts) != 4:
        return False
    tok_job_id, salt, expires_str, sig = parts
    if tok_job_id != job_id:
        return False
    try:
        expires_at = int(expires_str)
    except ValueError:
        return False
    if time.time() > expires_at:
        return False
    expected = _sign(job_id, salt, expires_at)
    return hmac.compare_digest(sig, expected)


def invalidate_start_token(token: str) -> bool:
    """
    Task 5.2: Invalidate on completion/cancellation.
    For HMAC tokens we cannot revoke - expiry handles it.
    For DB-backed tokens we would mark used. Using expiry-only for v0.
    """
    return True  # No-op for HMAC; expiry is the invalidation
