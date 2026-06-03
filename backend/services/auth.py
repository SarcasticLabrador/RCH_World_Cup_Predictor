"""Authentication logic: whitelist checks, user provisioning and magic links.

Endpoints (api/routes/auth.py) stay thin; the rules live here.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.db.models import MagicLink, User
from backend.security import generate_magic_token, hash_token


def is_whitelisted(email: str) -> bool:
    """True if the address matches a whitelist entry.

    Entries beginning with '@' match any address on that domain; other entries
    must match the full address exactly. An empty whitelist allows no one.
    """
    email = email.strip().lower()
    entries = get_settings().whitelist_entries
    for entry in entries:
        if entry.startswith("@"):
            if email.endswith(entry):
                return True
        elif email == entry:
            return True
    return False


def get_or_create_user(db: Session, email: str) -> User:
    email = email.strip().lower()
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(email=email, is_admin=email in get_settings().admin_email_entries)
        db.add(user)
        db.flush()
    return user


def create_magic_link(db: Session, user: User) -> str:
    """Create a single-use magic link and return the raw token (for the URL)."""
    settings = get_settings()
    raw, token_hash = generate_magic_token()
    expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.magic_link_ttl_hours)
    db.add(MagicLink(user_id=user.id, token_hash=token_hash, expires_at=expires_at))
    db.flush()
    return raw


def build_magic_url(raw_token: str) -> str:
    base = get_settings().app_base_url.rstrip("/")
    return f"{base}/?token={raw_token}"


def consume_magic_link(db: Session, raw_token: str) -> User | None:
    """Validate a raw token. If valid+unused+unexpired, mark used and return user."""
    token_hash = hash_token(raw_token)
    link = db.scalar(select(MagicLink).where(MagicLink.token_hash == token_hash))
    if link is None or link.used:
        return None

    expires_at = link.expires_at
    if expires_at.tzinfo is None:  # SQLite returns naive datetimes
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        return None

    link.used = True
    db.flush()
    return db.get(User, link.user_id)
