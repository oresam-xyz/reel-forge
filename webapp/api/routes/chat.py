"""Conversational assistant endpoint — brand creation and video campaign setup."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from webapp.api.auth import get_current_user
from webapp.db.database import get_db

router = APIRouter(prefix="/api/chat", tags=["chat"])

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "anthropic/claude-haiku-4-5"

# haiku-4-5 pricing (USD per 1M tokens)
_INPUT_PRICE = 0.80
_OUTPUT_PRICE = 4.00

SYSTEM_PROMPT = """You are the Reel Forge assistant — you help users build content creator brands and generate short-form video ad campaigns through natural conversation.

You have tools to create brands, create campaigns, suggest video angles, and queue video jobs.

## Efficiency rules
- Batch questions: ask 2-3 related things in one message. Never send a one-line question alone.
- State sensible defaults upfront and offer to proceed with them — don't ask permission for every field.
- If the user says "you decide", "suggest one", "use defaults", or similar — pick something concrete and proceed immediately.
- Once you have enough to act, confirm the key details in ONE message and call the tool. Don't ask for confirmation then ask again.

## Brand creation flow
Ask in two rounds maximum:
Round 1 — "What's your brand name (no spaces) and who is this creator? Give me a quick feel for their voice — are they direct/energetic/calm/etc?"
Round 2 — Confirm the full spec you'll use (including defaults for anything not mentioned) and call create_brand immediately.

Defaults to use unless told otherwise: reading_pace=medium, vocabulary=conversational, caption_style=word_by_word, voice_provider=kokoro, voice_id=af_heart, speed=1.0, pitch_adjust=0.0.

## Campaign creation flow
Ask in two rounds maximum:
Round 1 — "What are you selling, who's it for, and what's the main pain point?" (get product + audience + pain_point in one message)
Round 2 — "What's the CTA and preferred tone (direct/emotional/humorous)? I'll use kling-2.6-pro and 30s by default." Then call create_campaign immediately.

After creating, immediately call suggest_angles and show the results — don't ask if they want angles, just generate them.

## After angles are shown
Ask which angles to use (or "all of them") and call queue_jobs.

## Tone rules
- Conversational and practical, never stiff
- Give concrete examples when the user is unsure
- Move fast — users want videos, not an interview

## Reference
Available kokoro voice IDs: af_heart, af_sky, bf_emma, bf_isabella, am_adam, bm_george
Available visual models: kling-2.6-pro, kling-2.1-pro, kling-1.6-pro, seedance-1-pro, wan-pro, veo-3, minimax-video-01
Caption styles: word_by_word (karaoke), sentence, none"""

TOOLS = [
    {
        "name": "list_brands",
        "description": "List all existing brand names.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "create_brand",
        "description": "Create a new brand identity and save it to disk.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Brand name, no spaces"},
                "persona_character": {"type": "string", "description": "Who this creator is"},
                "persona_speaks_as": {"type": "string", "description": "Speaking style"},
                "persona_always_does": {"type": "array", "items": {"type": "string"}},
                "persona_never_does": {"type": "array", "items": {"type": "string"}},
                "tone_voice": {"type": "string"},
                "tone_reading_pace": {"type": "string", "enum": ["slow", "medium", "fast"]},
                "tone_vocabulary": {"type": "string"},
                "visual_aesthetic": {"type": "string"},
                "visual_colour_palette": {"type": "array", "items": {"type": "string"}},
                "visual_caption_style": {"type": "string", "enum": ["word_by_word", "sentence", "none"]},
                "visual_image_prompt_prefix": {"type": "string"},
                "voice_provider": {"type": "string", "enum": ["kokoro", "coqui"]},
                "voice_id": {"type": "string"},
                "voice_speed": {"type": "number"},
                "voice_pitch_adjust": {"type": "number"},
            },
            "required": ["name", "persona_character", "persona_speaks_as", "tone_voice"],
        },
    },
    {
        "name": "create_campaign",
        "description": "Create a new video ad campaign.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "brand_name": {"type": "string"},
                "product": {"type": "string"},
                "audience": {"type": "string"},
                "pain_point": {"type": "string"},
                "cta": {"type": "string"},
                "tone": {"type": "string"},
                "vertical": {"type": "string"},
                "visual_model": {"type": "string"},
                "target_duration": {"type": "integer"},
                "auto_approve": {"type": "boolean"},
            },
            "required": ["name", "brand_name", "product", "audience", "pain_point", "cta"],
        },
    },
    {
        "name": "suggest_angles",
        "description": "Generate 5 video hook angle suggestions for an existing campaign.",
        "input_schema": {
            "type": "object",
            "properties": {"campaign_id": {"type": "integer"}},
            "required": ["campaign_id"],
        },
    },
    {
        "name": "queue_jobs",
        "description": "Queue video generation jobs for a campaign with the given angles.",
        "input_schema": {
            "type": "object",
            "properties": {
                "campaign_id": {"type": "integer"},
                "angles": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["campaign_id", "angles"],
        },
    },
]


def _brands_dir() -> Path:
    from reelforge.config import load_config
    return Path(load_config().brands_dir)


def _execute_tool(name: str, args: dict, user: dict) -> tuple[dict, dict | None]:
    """Execute a tool call, return (result, action_or_None)."""

    if name == "list_brands":
        bd = _brands_dir()
        brands = []
        if bd.exists():
            brands = [
                d.name
                for d in sorted(bd.iterdir())
                if d.is_dir() and (d / "identity.json").exists()
            ]
        return {"brands": brands}, None

    if name == "create_brand":
        from reelforge.agent.brand import BrandIdentity
        from reelforge.providers.base import BrandIdentityData, Persona, Tone, VisualStyle, VoiceProfile

        def _to_list(v) -> list:
            if isinstance(v, list):
                return v
            if isinstance(v, str):
                return [s.strip() for s in v.replace(";", ",").split(",") if s.strip()]
            return []

        data = BrandIdentityData(
            name=args["name"],
            persona=Persona(
                character=args["persona_character"],
                speaks_as=args["persona_speaks_as"],
                always_does=_to_list(args.get("persona_always_does", [])),
                never_does=_to_list(args.get("persona_never_does", [])),
            ),
            tone=Tone(
                voice=args["tone_voice"],
                reading_pace=args.get("tone_reading_pace", "medium"),
                vocabulary=args.get("tone_vocabulary", "conversational"),
            ),
            visual_style=VisualStyle(
                aesthetic=args.get("visual_aesthetic", ""),
                colour_palette=args.get("visual_colour_palette", []),
                caption_style=args.get("visual_caption_style", "word_by_word"),
                image_prompt_prefix=args.get("visual_image_prompt_prefix", ""),
            ),
            voice_profile=VoiceProfile(
                provider=args.get("voice_provider", "kokoro"),
                voice_id=args.get("voice_id", "af_heart"),
                speed=args.get("voice_speed", 1.0),
                pitch_adjust=args.get("voice_pitch_adjust", 0.0),
            ),
        )
        BrandIdentity.save(_brands_dir(), data)
        return {"ok": True, "brand_name": args["name"]}, None

    if name == "create_campaign":
        brief = {
            "product": args["product"],
            "audience": args["audience"],
            "pain_point": args["pain_point"],
            "cta": args["cta"],
            "tone": args.get("tone", "direct"),
            "vertical": args.get("vertical", ""),
        }
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO campaigns (user_id, name, brief, brand_name, auto_approve, visual_model, target_duration)
                    VALUES (%s, %s, %s::jsonb, %s, %s, %s, %s)
                    RETURNING id, name
                    """,
                    (
                        user["id"], args["name"], json.dumps(brief), args["brand_name"],
                        args.get("auto_approve", False), args.get("visual_model", "kling-2.6-pro"),
                        args.get("target_duration", 30),
                    ),
                )
                row = dict(cur.fetchone())
            conn.commit()
        return {"ok": True, "campaign_id": row["id"], "campaign_name": row["name"]}, \
               {"type": "navigate", "path": f"/campaigns/{row['id']}"}

    if name == "suggest_angles":
        campaign_id = args["campaign_id"]
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT brief FROM campaigns WHERE id = %s AND user_id = %s",
                    (campaign_id, user["id"]),
                )
                row = cur.fetchone()
        if not row:
            return {"error": "Campaign not found"}, None
        brief = row["brief"]

        prompt = f"""You are a direct-response copywriter for short-form video ads.

Campaign brief:
- Product: {brief.get('product', '')}
- Audience: {brief.get('audience', '')}
- Pain point: {brief.get('pain_point', '')}
- CTA: {brief.get('cta', '')}
- Tone: {brief.get('tone', 'direct')}

Generate 5 distinct opening hooks. Each is one sentence — the first line spoken in the video.
Rules: vary the angle (question/claim/story/stat/challenge), specific not generic, write to ONE person, no banned words (professional, solution, leverage, transform, journey, seamless), don't mention the product or CTA.

Return ONLY valid JSON: {{"angles": ["hook1", "hook2", "hook3", "hook4", "hook5"]}}"""

        api_key = os.environ.get("OPENROUTER_API_KEY", "")
        resp = httpx.post(
            OPENROUTER_URL,
            headers={"Authorization": f"Bearer {api_key}", "HTTP-Referer": "https://oresam.xyz", "Content-Type": "application/json"},
            json={"model": MODEL, "messages": [{"role": "user", "content": prompt}], "response_format": {"type": "json_object"}},
            timeout=30,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"].strip()
        if content.startswith("```"):
            content = content.split("```", 2)[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.rsplit("```", 1)[0].strip()
        angles = json.loads(content)["angles"]
        return {"angles": angles[:5]}, None

    if name == "queue_jobs":
        campaign_id = args["campaign_id"]
        angles = args["angles"]
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM campaigns WHERE id = %s AND user_id = %s",
                    (campaign_id, user["id"]),
                )
                if not cur.fetchone():
                    return {"error": "Campaign not found"}, None
                for angle in angles:
                    cur.execute(
                        "INSERT INTO jobs (campaign_id, angle) VALUES (%s, %s)",
                        (campaign_id, angle),
                    )
            conn.commit()
        return {"ok": True, "jobs_created": len(angles)}, \
               {"type": "navigate", "path": f"/campaigns/{campaign_id}"}

    return {"error": f"Unknown tool: {name}"}, None


def _needs_approval(text: str) -> bool:
    """Return True if the assistant reply is waiting for user confirmation."""
    t = text.strip()
    if t.endswith("?"):
        return True
    patterns = [
        r"\bshall i\b", r"\bwould you like\b", r"\bgo ahead\b", r"\bconfirm\b",
        r"\bready to\b", r"\bshould i\b", r"\bwant me to\b", r"\bok to\b",
    ]
    lower = t.lower()
    return any(re.search(p, lower) for p in patterns)


def _calc_cost(usage: dict) -> float:
    prompt_tokens = usage.get("prompt_tokens", 0)
    completion_tokens = usage.get("completion_tokens", 0)
    return (prompt_tokens * _INPUT_PRICE + completion_tokens * _OUTPUT_PRICE) / 1_000_000


def _save_session(user_id: int, brand_name: str, messages: list, extra_cost: float) -> None:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO chat_sessions (user_id, brand_name, messages, cost_usd)
                VALUES (%s, %s, %s::jsonb, %s)
                ON CONFLICT (user_id, brand_name) DO UPDATE
                SET messages = EXCLUDED.messages,
                    cost_usd = chat_sessions.cost_usd + EXCLUDED.cost_usd
                """,
                (user_id, brand_name, json.dumps(messages), extra_cost),
            )
        conn.commit()


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    brand_name: str = "__inbox__"


class ChatResponse(BaseModel):
    reply: str
    action: dict | None = None
    awaiting_approval: bool = False


class SessionSummary(BaseModel):
    brand_name: str
    cost_usd: float
    updated_at: str


@router.get("/sessions", response_model=list[SessionSummary])
def list_sessions(user=Depends(get_current_user)):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT brand_name, cost_usd, updated_at FROM chat_sessions WHERE user_id = %s ORDER BY updated_at DESC",
                (user["id"],),
            )
            rows = cur.fetchall()
    return [{"brand_name": r["brand_name"], "cost_usd": float(r["cost_usd"]), "updated_at": r["updated_at"].isoformat()} for r in rows]


@router.get("/history/{brand_name}", response_model=dict)
def get_history(brand_name: str, user=Depends(get_current_user)):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT messages FROM chat_sessions WHERE user_id = %s AND brand_name = %s",
                (user["id"], brand_name),
            )
            row = cur.fetchone()
    messages = row["messages"] if row else []
    return {"messages": messages}


@router.post("", response_model=ChatResponse)
def chat(body: ChatRequest, user=Depends(get_current_user)):
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        raise HTTPException(status_code=500, detail="OPENROUTER_API_KEY not set")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "https://oresam.xyz",
        "Content-Type": "application/json",
    }

    or_tools = [{"type": "function", "function": {
        "name": t["name"],
        "description": t["description"],
        "parameters": t["input_schema"],
    }} for t in TOOLS]

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages += [{"role": m.role, "content": m.content} for m in body.messages]
    action: dict | None = None
    total_cost = 0.0
    max_rounds = 8

    for _ in range(max_rounds):
        resp = httpx.post(
            OPENROUTER_URL,
            headers=headers,
            json={"model": MODEL, "messages": messages, "tools": or_tools},
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        choice = data["choices"][0]
        msg = choice["message"]
        finish = choice.get("finish_reason")

        if usage := data.get("usage"):
            total_cost += _calc_cost(usage)

        if finish == "tool_calls" or msg.get("tool_calls"):
            messages.append(msg)
            for tc in msg.get("tool_calls", []):
                fn = tc["function"]
                args = json.loads(fn.get("arguments") or "{}")
                result, act = _execute_tool(fn["name"], args, user)
                if act:
                    action = act
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": json.dumps(result),
                })
        else:
            reply = msg.get("content", "")
            # Persist: save only user+assistant turns (strip system + tool messages)
            saveable = [
                {"role": m["role"], "content": m["content"]}
                for m in messages[1:]  # skip system prompt
                if m["role"] in ("user", "assistant") and isinstance(m.get("content"), str)
            ]
            # Append this new assistant reply
            saveable.append({"role": "assistant", "content": reply})
            _save_session(user["id"], body.brand_name, saveable, total_cost)
            return ChatResponse(
                reply=reply,
                action=action,
                awaiting_approval=_needs_approval(reply),
            )

    raise HTTPException(status_code=500, detail="Chat loop exceeded max rounds")
