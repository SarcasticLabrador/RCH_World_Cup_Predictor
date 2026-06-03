"""Security helpers: magic-link tokens and signed session tokens.

Magic-link tokens are random, single-use, and stored only as SHA-256 hashes
(the raw token lives only in the emailed URL). Session tokens are stateless,
signed with SECRET_KEY via itsdangerous, and carry an expiry.
"""
from __future__ import annotations

import hashlib
import secrets

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from backend.config import get_settings

_SESSION_SALT = "wcp-session-v1"


def generate_magic_token() -> tuple[str, str]:
    """Return (raw_token, token_hash). Store the hash; email the raw token."""
    raw = secrets.token_urlsafe(32)
    return raw, hash_token(raw)


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _serializer() -> URLSafeTimedSerializer:
    settings = get_settings()
    return URLSafeTimedSerializer(settings.secret_key, salt=_SESSION_SALT)


def make_session_token(user_id) -> str:
    """Create a signed session token embedding the user id."""
    return _serializer().dumps({"uid": str(user_id)})


def read_session_token(token: str) -> str | None:
    """Return the user id from a valid, unexpired token, else None."""
    settings = get_settings()
    max_age = settings.session_ttl_days * 24 * 3600
    try:
        data = _serializer().loads(token, max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None
    return data.get("uid")
