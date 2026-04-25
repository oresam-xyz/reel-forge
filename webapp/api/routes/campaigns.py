"""Campaign CRUD endpoints."""

from __future__ import annotations
import os
import json

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from webapp.api.auth import get_current_user
from webapp.db.database import get_db

router = APIRouter(prefix="/api/campaigns", tags=["campaigns"])


class BriefIn(BaseModel):
    product: str
    audience: str
    pain_point: str
    cta: str
    tone: str = "direct"
    vertical: str = ""


class CampaignIn(BaseModel):
    name: str
    brief: BriefIn
    brand_name: str
    auto_approve: bool = False
    visual_model: str = "kling-2.6-pro"
    target_duration: int = 30


class QueueJobsIn(BaseModel):
    angles: list[str]


@router.post("", status_code=201)
def create_campaign(body: CampaignIn, user=Depends(get_current_user)):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO campaigns (user_id, name, brief, brand_name, auto_approve, visual_model, target_duration)
                VALUES (%s, %s, %s::jsonb, %s, %s, %s, %s)
                RETURNING id, name, brief, brand_name, auto_approve, visual_model, target_duration, created_at
                """,
                (user["id"], body.name, body.brief.model_dump_json(), body.brand_name, body.auto_approve, body.visual_model, body.target_duration),
            )
            row = dict(cur.fetchone())
        conn.commit()
    return row


@router.get("")
def list_campaigns(user=Depends(get_current_user)):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT c.id, c.name, c.brief, c.brand_name, c.auto_approve, c.visual_model, c.target_duration, c.created_at,
                    COUNT(j.id) FILTER (WHERE j.status = 'pending')       AS pending,
                    COUNT(j.id) FILTER (WHERE j.status = 'running')       AS running,
                    COUNT(j.id) FILTER (WHERE j.status = 'review_pending') AS review_pending,
                    COUNT(j.id) FILTER (WHERE j.status = 'complete')      AS complete,
                    COUNT(j.id) FILTER (WHERE j.status = 'failed')        AS failed,
                    SUM(j.cost_usd)                                        AS total_cost_usd
                FROM campaigns c
                LEFT JOIN jobs j ON j.campaign_id = c.id
                WHERE c.user_id = %s
                GROUP BY c.id
                ORDER BY c.created_at DESC
                """,
                (user["id"],),
            )
            return [dict(r) for r in cur.fetchall()]


@router.get("/{campaign_id}")
def get_campaign(campaign_id: int, user=Depends(get_current_user)):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, brief, brand_name, auto_approve, visual_model, target_duration, created_at FROM campaigns WHERE id = %s AND user_id = %s",
                (campaign_id, user["id"]),
            )
            campaign = cur.fetchone()
            if not campaign:
                raise HTTPException(status_code=404, detail="Campaign not found")
            cur.execute(
                "SELECT * FROM jobs WHERE campaign_id = %s ORDER BY created_at DESC",
                (campaign_id,),
            )
            jobs = [dict(r) for r in cur.fetchall()]
    return {**dict(campaign), "jobs": jobs}


@router.delete("/{campaign_id}", status_code=204)
def delete_campaign(campaign_id: int, user=Depends(get_current_user)):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM campaigns WHERE id = %s AND user_id = %s",
                (campaign_id, user["id"]),
            )
        conn.commit()


@router.post("/{campaign_id}/suggest-angles")
def suggest_angles(campaign_id: int, user=Depends(get_current_user)):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT brief FROM campaigns WHERE id = %s AND user_id = %s",
                (campaign_id, user["id"]),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Campaign not found")
            brief = row["brief"]

    vertical = brief.get('vertical') or 'general'
    prompt = f"""You write opening hooks for short-form video ads (TikTok / Instagram Reels). \
Your hooks are the first thing someone hears — they must stop the scroll in under 2 seconds.

PRODUCT: {brief['product']}
AUDIENCE: {brief['audience']}
PAIN: {brief['pain_point']}
CTA: {brief['cta']}
TONE: {brief['tone']}
VERTICAL: {vertical}

Write exactly 5 hooks. Rules:
1. Each hook is ONE sentence, spoken aloud, max 12 words.
2. Each must use a DIFFERENT archetype from this list — use each archetype once:
   - ACCUSATION: call out a mistake they're actively making right now
   - SPECIFIC FEAR: name the exact moment they dread (a lost job, a missed call, a competitor winning)
   - COST: put a real number or time cost on the pain ("3 enquiries a week", "4 hours a day")
   - CONTRAST: imply before/after without spelling it out ("used to" / "now" / "still")
   - CHALLENGE: directly dare them ("If your phone isn't ringing, this is why.")
3. Write like you're speaking to ONE person — use "you" and "your", never "businesses" or "entrepreneurs".
4. BANNED words: professional, solution, leverage, results, presence, digital, empower, transform, journey, seamless.
5. Be concrete and specific — name real things from their day (quotes, enquiries, spreadsheets, callbacks).
6. Do NOT mention the product name or the CTA in the hook — the hook earns the pitch.

Return ONLY valid JSON: {{"angles": ["hook1", "hook2", "hook3", "hook4", "hook5"]}}"""

    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    try:
        resp = httpx.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "HTTP-Referer": "https://oresam.xyz",
                "Content-Type": "application/json",
            },
            json={
                "model": "anthropic/claude-haiku-4-5",
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"},
            },
            timeout=30,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        # Strip markdown fences if the model wraps JSON in ```json ... ```
        content = content.strip()
        if content.startswith("```"):
            content = content.split("```", 2)[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.rsplit("```", 1)[0].strip()
        angles = json.loads(content)["angles"]
        return {"angles": angles[:5]}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM error: {e}")


@router.post("/{campaign_id}/jobs", status_code=201)
def queue_jobs(campaign_id: int, body: QueueJobsIn, user=Depends(get_current_user)):
    if not body.angles:
        raise HTTPException(status_code=422, detail="At least one angle required")
    with get_db() as conn:
        with conn.cursor() as cur:
            # Verify ownership
            cur.execute(
                "SELECT id FROM campaigns WHERE id = %s AND user_id = %s",
                (campaign_id, user["id"]),
            )
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Campaign not found")
            created = []
            for angle in body.angles:
                cur.execute(
                    "INSERT INTO jobs (campaign_id, angle) VALUES (%s, %s) RETURNING id, angle, status",
                    (campaign_id, angle),
                )
                created.append(dict(cur.fetchone()))
        conn.commit()
    return created
