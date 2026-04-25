"""Job CRUD and control endpoints."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel

from webapp.api.auth import get_current_user
from webapp.db.database import get_db

router = APIRouter(prefix="/api/jobs", tags=["jobs"])

# Absolute path so relative output_path values resolve correctly
_REELFORGE_ROOT = Path(__file__).resolve().parents[3]
PROJECTS_ROOT = Path(os.environ.get("REELFORGE_PROJECTS_DIR", str(_REELFORGE_ROOT / "projects")))


def _get_job_for_user(job_id: int, user: dict) -> dict:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT j.* FROM jobs j
                JOIN campaigns c ON c.id = j.campaign_id
                WHERE j.id = %s AND c.user_id = %s
                """,
                (job_id, user["id"]),
            )
            row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    return dict(row)


@router.get("/{job_id}")
def get_job(job_id: int, user=Depends(get_current_user)):
    return _get_job_for_user(job_id, user)


class ApproveIn(BaseModel):
    feedback: str = ""


@router.post("/{job_id}/approve")
def approve_job(job_id: int, body: ApproveIn, user=Depends(get_current_user)):
    job = _get_job_for_user(job_id, user)
    if job["status"] != "review_pending":
        raise HTTPException(status_code=409, detail="Job is not awaiting review")

    with get_db() as conn:
        with conn.cursor() as cur:
            # Store optional feedback in plan_json and set status back to pending
            # so the worker resumes from the next phase
            if body.feedback:
                cur.execute(
                    """
                    UPDATE jobs
                    SET status = 'pending',
                        plan_json = plan_json || jsonb_build_object('_feedback', %s)
                    WHERE id = %s
                    """,
                    (body.feedback, job_id),
                )
            else:
                cur.execute(
                    "UPDATE jobs SET status = 'pending' WHERE id = %s",
                    (job_id,),
                )
        conn.commit()
    return {"ok": True}


class RejectIn(BaseModel):
    feedback: str


@router.post("/{job_id}/reject")
def reject_job(job_id: int, body: RejectIn, user=Depends(get_current_user)):
    job = _get_job_for_user(job_id, user)
    if job["status"] != "review_pending":
        raise HTTPException(status_code=409, detail="Job is not awaiting review")

    with get_db() as conn:
        with conn.cursor() as cur:
            # Reset to pending with feedback so worker re-runs planning
            cur.execute(
                """
                UPDATE jobs
                SET status = 'pending',
                    phase = 'planning',
                    plan_json = jsonb_build_object('_feedback', %s)
                WHERE id = %s
                """,
                (body.feedback, job_id),
            )
        conn.commit()
    return {"ok": True}


@router.post("/{job_id}/retry")
def retry_job(job_id: int, user=Depends(get_current_user)):
    job = _get_job_for_user(job_id, user)
    if job["status"] != "failed":
        raise HTTPException(status_code=409, detail="Job has not failed")

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE jobs SET status = 'pending', error = NULL WHERE id = %s",
                (job_id,),
            )
        conn.commit()
    return {"ok": True}


def _get_user_token_or_query(request: Request, token: str | None = None) -> dict:
    """Auth for media endpoints — accepts JWT via header or ?token= query param."""
    from webapp.api.auth import decode_token
    raw = token or request.headers.get("authorization", "").removeprefix("Bearer ").strip()
    if not raw:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return decode_token(raw)


@router.get("/{job_id}/phases/{phase_name}")
def get_phase_data(job_id: int, phase_name: str, user=Depends(get_current_user)):
    """Return the artefact produced by a completed pipeline phase."""
    import json

    job = _get_job_for_user(job_id, user)
    project_id = job.get("project_id")
    if not project_id:
        raise HTTPException(status_code=404, detail="Project not yet created")

    proj_dir = PROJECTS_ROOT / project_id

    if phase_name == "research":
        path = proj_dir / "research.json"
        if not path.exists():
            raise HTTPException(status_code=404, detail="research.json not found")
        return json.loads(path.read_text())

    elif phase_name in ("planning", "review"):
        # Prefer DB snapshot (already loaded), fall back to disk
        if job.get("plan_json"):
            return job["plan_json"]
        path = proj_dir / "plan.json"
        if not path.exists():
            raise HTTPException(status_code=404, detail="plan.json not found")
        return json.loads(path.read_text())

    elif phase_name == "script":
        path = proj_dir / "assets" / "script.json"
        if not path.exists():
            raise HTTPException(status_code=404, detail="script.json not found")
        return json.loads(path.read_text())

    elif phase_name == "assets":
        assets_dir = proj_dir / "assets"
        if not assets_dir.exists():
            raise HTTPException(status_code=404, detail="assets dir not found")
        files = []
        for f in sorted(assets_dir.iterdir()):
            if f.suffix in (".mp4", ".wav", ".mp3", ".png", ".jpg"):
                files.append({"name": f.name, "size_bytes": f.stat().st_size, "type": f.suffix.lstrip(".")})
        return {"files": files}

    elif phase_name == "render":
        captions_path = proj_dir / "assets" / "captions.json"
        result: dict = {}
        if captions_path.exists():
            result["captions"] = json.loads(captions_path.read_text())
        output = proj_dir / "output.mp4"
        if output.exists():
            result["output_size_bytes"] = output.stat().st_size
        return result

    else:
        raise HTTPException(status_code=400, detail=f"Unknown phase: {phase_name}")


@router.get("/{job_id}/video")
def stream_video(job_id: int, request: Request, token: str | None = None):
    user = _get_user_token_or_query(request, token)
    job = _get_job_for_user(job_id, user)
    if not job.get("output_path"):
        raise HTTPException(status_code=404, detail="Video not yet available")

    # Resolve relative paths against the reel-forge root
    raw = Path(job["output_path"])
    path = raw if raw.is_absolute() else _REELFORGE_ROOT / raw
    if not path.exists():
        raise HTTPException(status_code=404, detail="Video file not found on disk")

    file_size = path.stat().st_size
    range_header = request.headers.get("range")

    if range_header:
        # Parse "bytes=start-end"
        byte_range = range_header.replace("bytes=", "").strip()
        start_str, _, end_str = byte_range.partition("-")
        start = int(start_str) if start_str else 0
        end = int(end_str) if end_str else file_size - 1
        end = min(end, file_size - 1)
        length = end - start + 1

        def iter_file():
            with open(path, "rb") as f:
                f.seek(start)
                remaining = length
                chunk = 65536
                while remaining > 0:
                    data = f.read(min(chunk, remaining))
                    if not data:
                        break
                    remaining -= len(data)
                    yield data

        return StreamingResponse(
            iter_file(),
            status_code=206,
            media_type="video/mp4",
            headers={
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(length),
                "Content-Disposition": f'inline; filename="job-{job_id}.mp4"',
            },
        )

    def iter_full():
        with open(path, "rb") as f:
            while chunk := f.read(65536):
                yield chunk

    return StreamingResponse(
        iter_full(),
        media_type="video/mp4",
        headers={
            "Accept-Ranges": "bytes",
            "Content-Length": str(file_size),
            "Content-Disposition": f'inline; filename="job-{job_id}.mp4"',
        },
    )
