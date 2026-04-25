"""FastAPI application entry point."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=True)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from webapp.api import auth
from webapp.api.routes import campaigns, jobs, me, brands
from webapp.db.database import init_db
from webapp.worker.runner import start_worker

app = FastAPI(title="Reel-Forge")

FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:5173")
CALLBACK_URL = os.environ.get("GOOGLE_REDIRECT_URI", f"{FRONTEND_URL}/auth/callback")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(campaigns.router)
app.include_router(jobs.router)
app.include_router(me.router)
app.include_router(brands.router)


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    start_worker()


@app.get("/auth/google")
def google_login():
    url = auth.google_login_url(CALLBACK_URL)
    return RedirectResponse(url)


@app.get("/auth/google/callback")
def google_callback(code: str):
    user_info = auth.exchange_code_for_user(code, CALLBACK_URL)
    user_id = auth.upsert_user(user_info)
    token = auth.create_jwt(user_id, user_info["email"])
    # Redirect frontend — token passed as query param, stored in localStorage
    return RedirectResponse(f"{FRONTEND_URL}/auth/callback?token={token}")
