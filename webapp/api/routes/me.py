"""Current-user profile endpoints."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from webapp.api.auth import get_current_user
from webapp.db.database import get_db

router = APIRouter(prefix="/api/me", tags=["me"])


class MePatch(BaseModel):
    name: str | None = None
    settings: dict | None = None


@router.get("")
def get_me(user=Depends(get_current_user)):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, email, created_at, settings FROM users WHERE id = %s",
                (user["id"],),
            )
            return dict(cur.fetchone())


@router.patch("")
def patch_me(body: MePatch, user=Depends(get_current_user)):
    if body.name is None and body.settings is None:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, name, email, created_at, settings FROM users WHERE id = %s",
                    (user["id"],),
                )
                return dict(cur.fetchone())

    with get_db() as conn:
        with conn.cursor() as cur:
            if body.name is not None and body.settings is not None:
                cur.execute(
                    "UPDATE users SET name = %s, settings = settings || %s::jsonb WHERE id = %s",
                    (body.name, json.dumps(body.settings), user["id"]),
                )
            elif body.name is not None:
                cur.execute(
                    "UPDATE users SET name = %s WHERE id = %s",
                    (body.name, user["id"]),
                )
            else:
                cur.execute(
                    "UPDATE users SET settings = settings || %s::jsonb WHERE id = %s",
                    (json.dumps(body.settings), user["id"]),
                )
            cur.execute(
                "SELECT id, name, email, created_at, settings FROM users WHERE id = %s",
                (user["id"],),
            )
            result = dict(cur.fetchone())
        conn.commit()
    return result
