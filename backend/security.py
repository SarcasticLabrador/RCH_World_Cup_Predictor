"""Security helpers: password hashing, magic-link tokens and signed session tokens."""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from backend.config import get_settings

_SESSION_SALT = "wcp-session-v1"
_ITERATIONS = 260_000


# --- Password hashing (stdlib pbkdf2 — no extra dependency) -----------------

def hash_password(plain: str) -> str:
    salt = os.urandom(32)
    key = hashlib.pbkdf2_hmac("sha256", plain.encode(), salt, _ITERATIONS)
    return salt.hex() + ":" + key.hex()


def verify_password(plain: str, stored: str) -> bool:
    try:
        salt_hex, key_hex = stored.split(":")
    except ValueError:
        return False
    salt = bytes.fromhex(salt_hex)
    key = hashlib.pbkdf2_hmac("sha256", plain.encode(), salt, _ITERATIONS)
    return hmac.compare_digest(key.hex(), key_hex)


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
