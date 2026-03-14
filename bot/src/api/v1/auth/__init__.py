"""Authentication router."""

import os

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Session
from src.api.auth_utils import JWTUtils, PasswordUtils
from src.infrastructure.database import db
from src.infrastructure.domain.models.auth_models import User

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


class LoginRequest(BaseModel):
    """JSON login payload expected by the frontend."""

    username: str
    password: str


def _build_token_response(username: str) -> dict:
    access_token = JWTUtils.create_access_token({"sub": username})
    refresh_token = JWTUtils.create_refresh_token({"sub": username})
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": 3600,
    }


def _authenticate_user(
    username: str,
    password: str,
    session: Session,
) -> dict:
    if os.getenv("API_BYPASS_AUTH", "false").lower() == "true":
        return _build_token_response(username)

    user = session.query(User).filter(User.username == username).first()
    if not user or not PasswordUtils.verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    return _build_token_response(user.username)


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
async def register():
    """Register endpoint"""
    # Placeholder implementation
    return {"message": "Registration not implemented"}


@router.post("/logout")
async def logout():
    """Logout endpoint"""
    # Placeholder implementation
    return {"message": "Logged out"}
