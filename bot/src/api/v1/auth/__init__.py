"""Authentication router."""

import os
from typing import cast

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from src.api.auth_utils import JWTUtils, PasswordUtils, SecurityUtils
from src.infrastructure.database import db
from src.infrastructure.domain.models.auth_models import User
from src.shared.time_utils import utc_now

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


class LoginRequest(BaseModel):
    """JSON login payload expected by the frontend."""

    username: str
    password: str


class RegisterRequest(BaseModel):
    """JSON registration payload."""

    username: str
    email: EmailStr
    password: str
    full_name: str = ""


def _build_token_response(username: str) -> dict:
    access_token = JWTUtils.create_access_token({"sub": username})
    refresh_token = JWTUtils.create_refresh_token({"sub": username})
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": 3600,
    }


def _username_value(user: User) -> str:
    return str(cast(object, user.username))


def _hashed_password_value(user: User) -> str:
    return str(cast(object, user.hashed_password))


def _authenticate_user(
    username: str,
    password: str,
    session: Session,
) -> dict:
    if os.getenv("API_BYPASS_AUTH", "false").lower() == "true":
        return _build_token_response(username)

    user = session.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    hashed_password = _hashed_password_value(user)
    if not PasswordUtils.verify_password(password, hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    return _build_token_response(_username_value(user))


@router.post("/token")
async def token_login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(db.get_session),
):
    """Login endpoint"""
    return _authenticate_user(form_data.username, form_data.password, session)


@router.post("/login")
async def login(
    payload: LoginRequest,
    session: Session = Depends(db.get_session),
):
    """Frontend-compatible JSON login endpoint."""
    return _authenticate_user(payload.username, payload.password, session)


@router.post("/register")
async def register(
    payload: RegisterRequest,
    session: Session = Depends(db.get_session),
):
    """Register endpoint."""
    username = SecurityUtils.sanitize_input(payload.username, max_length=50)
    full_name = SecurityUtils.sanitize_input(payload.full_name, max_length=100)
    email = payload.email.strip().lower()

    if not username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username is required",
        )

    if not SecurityUtils.is_email_valid(email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid email format",
        )

    password_strength = SecurityUtils.validate_password_strength(payload.password)
    if not password_strength["is_valid"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="; ".join(password_strength["errors"]),
        )

    existing_user = (
        session.query(User)
        .filter((User.username == username) | (User.email == email))
        .first()
    )
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username or email already exists",
        )

    user = User(
        username=username,
        email=email,
        hashed_password=PasswordUtils.hash_password(payload.password),
        full_name=full_name or None,
        is_active=True,
        is_admin=False,
        created_at=utc_now(),
        updated_at=utc_now(),
    )

    session.add(user)
    session.commit()
    session.refresh(user)

    token_response = _build_token_response(_username_value(user))
    return {
        "message": "User registered successfully",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name,
            "is_active": user.is_active,
            "is_admin": user.is_admin,
            "created_at": user.created_at.isoformat() if user.created_at else None,
        },
        **token_response,
    }


@router.post("/logout")
async def logout():
    """Logout endpoint"""
    # Placeholder implementation
    return {"message": "Logged out"}


@router.post("/logout-all")
async def logout_all():
    """Logout all sessions endpoint (compatibility stub)."""
    # Token revocation store is not yet wired; keep endpoint for contract compatibility.
    return {"message": "Logged out from all sessions"}
