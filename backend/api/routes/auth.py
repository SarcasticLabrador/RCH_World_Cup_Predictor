"""Auth endpoints: request login link, verify, fetch profile, update profile."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.api.deps import get_current_user
from backend.config import get_settings
from backend.db.base import get_db
from backend.db.models import User
from backend.schemas import (
    GenericMessageOut,
    RequestLinkIn,
    UpdateProfileIn,
    UserOut,
    VerifyOut,
)
from backend.security import make_session_token
from backend.services import auth as auth_service
from backend.services.email import get_email_sender
from backend.services.email_templates import login_email

router = APIRouter(prefix="/auth", tags=["auth"])

# Deliberately generic so we never reveal who is/isn't whitelisted.
_GENERIC_MSG = "If your email is eligible, a sign-in link has been sent."


@router.post("/request-link", response_model=GenericMessageOut)
def request_link(body: RequestLinkIn, db: Session = Depends(get_db)) -> GenericMessageOut:
    settings = get_settings()
    email = str(body.email)

    if auth_service.is_whitelisted(email):
        user = auth_service.get_or_create_user(db, email)
        raw = auth_service.create_magic_link(db, user)
        db.commit()

        url = auth_service.build_magic_url(raw)
        subject, html, text = login_email(url, settings.magic_link_ttl_hours)
        get_email_sender(settings).send(email, subject, html, text)

    return GenericMessageOut(message=_GENERIC_MSG)


@router.get("/verify", response_model=VerifyOut)
def verify(token: str, db: Session = Depends(get_db)) -> VerifyOut:
    from fastapi import HTTPException, status

    user = auth_service.consume_magic_link(db, token)
    if user is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired link")
    db.commit()

    return VerifyOut(session_token=make_session_token(user.id), user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(current: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(current)


@router.post("/me", response_model=UserOut)
def update_me(
    body: UpdateProfileIn,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserOut:
    current.display_name = body.display_name.strip()[:80]
    db.commit()
    db.refresh(current)
    return UserOut.model_validate(current)
