import os
import secrets

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

router = APIRouter()

# Demo-grade credential check - no user database, just a single shared login
# gating the dashboard. Tokens are opaque and live in memory only (lost on
# backend restart), which is fine for a single-process demo deployment.
AUTH_USERNAME = os.getenv("AUTH_USERNAME", "admin")
AUTH_PASSWORD = os.getenv("AUTH_PASSWORD", "hawkeye2026")

valid_tokens: set[str] = set()


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str


@router.post("/auth/login", response_model=LoginResponse)
def login(payload: LoginRequest):
    if payload.username != AUTH_USERNAME or payload.password != AUTH_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = secrets.token_hex(24)
    valid_tokens.add(token)
    return LoginResponse(token=token)


@router.post("/auth/logout")
def logout(authorization: str | None = Header(default=None)):
    token = (authorization or "").removeprefix("Bearer ").strip()
    valid_tokens.discard(token)
    return {"loggedOut": True}


def require_auth(authorization: str | None = Header(default=None)) -> str:
    token = (authorization or "").removeprefix("Bearer ").strip()
    if not token or token not in valid_tokens:
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization token")
    return token
