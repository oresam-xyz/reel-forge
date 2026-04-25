"""Brand identity read/write endpoints."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from webapp.api.auth import get_current_user
from webapp.db.database import get_db

router = APIRouter(prefix="/api/brands", tags=["brands"])


def _brands_dir() -> Path:
    from reelforge.config import load_config
    config = load_config()
    return Path(config.brands_dir)


def _validate_name(name: str) -> None:
    if "/" in name or ".." in name:
        raise HTTPException(status_code=400, detail="Invalid brand name")


@router.get("")
def list_brands(user=Depends(get_current_user)):
    brands_dir = _brands_dir()
    if not brands_dir.exists():
        return []
    return [
        d.name for d in sorted(brands_dir.iterdir())
        if d.is_dir() and (d / "identity.json").exists()
    ]


@router.get("/{name}")
def get_brand(name: str, user=Depends(get_current_user)):
    _validate_name(name)
    identity_path = _brands_dir() / name / "identity.json"
    if not identity_path.exists():
        raise HTTPException(status_code=404, detail="Brand not found")
    return json.loads(identity_path.read_text())


class BrandPatch(BaseModel):
    tone: dict | None = None
    voice_profile: dict | None = None
    visual_style: dict | None = None
    pronunciations: dict | None = None


@router.patch("/{name}")
def patch_brand(name: str, body: BrandPatch, user=Depends(get_current_user)):
    _validate_name(name)
    identity_path = _brands_dir() / name / "identity.json"
    if not identity_path.exists():
        raise HTTPException(status_code=404, detail="Brand not found")

    data = json.loads(identity_path.read_text())

    if body.tone is not None:
        data.setdefault("tone", {}).update(body.tone)
    if body.voice_profile is not None:
        data.setdefault("voice_profile", {}).update(body.voice_profile)
    if body.visual_style is not None:
        data.setdefault("visual_style", {}).update(body.visual_style)
    if body.pronunciations is not None:
        data["pronunciations"] = body.pronunciations

    # Validate via BrandIdentityData before writing
    from reelforge.providers.base import BrandIdentityData
    try:
        BrandIdentityData.model_validate(data)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Invalid brand data: {e}")

    identity_path.write_text(json.dumps(data, indent=2))
    return data
