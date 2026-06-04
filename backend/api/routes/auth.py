"""Auth endpoints: register, login, profile."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.api.deps import get_current_user
from backend.db.base import get_db
from backend.db.models import User
from backend.schemas import LoginIn, RegisterIn, UpdateProfileIn, UserOut, VerifyOut
from backend.security import make_session_token
from backend.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=VerifyOut, status_code=201)
def register(body: RegisterIn, db: Session = Depends(get_db)) -> VerifyOut:
    if not auth_service.is_whitelisted(str(body.email)):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Email address not on the invite list.")
    if auth_service.get_user_by_email(db, str(body.email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with that email already exists.")
    user = auth_service.register_user(db, str(body.email), body.password, body.display_name)
    db.commit()
    return VerifyOut(session_token=make_session_token(user.id), user=UserOut.model_validate(user))


@router.post("/login", response_model=VerifyOut)
def login(body: LoginIn, db: Session = Depends(get_db)) -> VerifyOut:
    user = auth_service.authenticate_user(db, str(body.email), body.password)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password.")
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
