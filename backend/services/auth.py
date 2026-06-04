"""Authentication logic: whitelist, password-based register/login."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.db.models import User
from backend.security import hash_password, verify_password


def is_whitelisted(email: str) -> bool:
    email = email.strip().lower()
    entries = get_settings().whitelist_entries
    for entry in entries:
        if entry.startswith("@"):
            if email.endswith(entry):
                return True
        elif email == entry:
            return True
    return False


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email.strip().lower()))


def register_user(db: Session, email: str, password: str, display_name: str) -> User:
    """Create a new user. Caller must verify whitelist and check for duplicates first."""
    email = email.strip().lower()
    user = User(
        email=email,
        display_name=display_name.strip()[:80],
        password_hash=hash_password(password),
        is_admin=email in get_settings().admin_email_entries,
    )
    db.add(user)
    db.flush()
    return user


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    """Return the user if credentials are valid, else None."""
    user = get_user_by_email(db, email)
    if user is None or not user.password_hash:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user
