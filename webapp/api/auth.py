"""Google OAuth2 login and JWT helpers."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from jose import JWTError, jwt

from webapp.db.database import get_db

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
JWT_SECRET = os.environ.get("JWT_SECRET", "change-me-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 24

_raw = os.environ.get("ALLOWED_EMAILS", "")
ALLOWED_EMAILS: set[str] = {e.strip().lower() for e in _raw.split(",") if e.strip()} if _raw else set()

_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)


def _google_auth_url(redirect_uri: str) -> str:
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return f"https://accounts.google.com/o/oauth2/v2/auth?{query}"


def google_login_url(redirect_uri: str) -> str:
    return _google_auth_url(redirect_uri)


def exchange_code_for_user(code: str, redirect_uri: str) -> dict:
    """Exchange auth code for ID token; verify and return user info dict."""
    resp = httpx.post(
        "https://oauth2.googleapis.com/token",
        data={
            "code": code,
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        },
    )
    resp.raise_for_status()
    tokens = resp.json()

    # Verify the ID token against Google's public keys
    info = id_token.verify_oauth2_token(
        tokens["id_token"],
        google_requests.Request(),
        GOOGLE_CLIENT_ID,
    )
    email = info["email"]
    if ALLOWED_EMAILS and email.lower() not in ALLOWED_EMAILS:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account not authorised")
    return {"google_sub": info["sub"], "email": email, "name": info.get("name", "")}


def upsert_user(user_info: dict) -> int:
    """Insert or update the user row; return the user id."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users (google_sub, email, name)
                VALUES (%(google_sub)s, %(email)s, %(name)s)
                ON CONFLICT (google_sub) DO UPDATE
                    SET email = EXCLUDED.email, name = EXCLUDED.name
                RETURNING id
                """,
                user_info,
            )
            row = cur.fetchone()
        conn.commit()
    return row["id"]


def create_jwt(user_id: int, email: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRY_HOURS)
    return jwt.encode(
        {"sub": str(user_id), "email": email, "exp": expire},
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return {"id": int(payload["sub"]), "email": payload["email"]}
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


def get_current_user(token: str | None = Depends(_oauth2_scheme)) -> dict:
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return decode_token(token)
