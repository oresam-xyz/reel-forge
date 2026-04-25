"""Background worker — polls for pending jobs and runs the reel-forge pipeline."""

from __future__ import annotations

import json
import logging
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from reelforge.agent.brand import BrandIdentity
from reelforge.agent.project import Project
from reelforge.agent.runner import instantiate_providers, run_pipeline
from reelforge.config import load_config
from reelforge.providers.base import ResearchNotes
from webapp.db.database import get_db

logger = logging.getLogger(__name__)

_POLL_INTERVAL = 5  # seconds


class _ReviewPending(Exception):
    """Sentinel raised by the web review phase override to pause the pipeline."""


def _web_review_phase(project, brand, providers):
    """Replace interactive CLI review with a DB-signalled pause."""
    raise _ReviewPending("Plan ready for web review")


def _brief_phase(brief: dict):
    """Return a phase_override function that injects the campaign brief as research."""
    def run(project, brand, providers):
        notes = ResearchNotes(
            queries=[],
            sources=[],
            key_facts=[
                f"Product: {brief.get('product', '')}",
                f"Target audience: {brief.get('audience', '')}",
                f"Pain point: {brief.get('pain_point', '')}",
                f"Call to action: {brief.get('cta', '')}",
                f"Angle: {brief.get('_angle', '')}",
                f"Tone: {brief.get('tone', 'direct')}",
                f"Vertical: {brief.get('vertical', '')}",
            ],
            completed_at=datetime.now(timezone.utc).isoformat(),
        )
        project.save_research(notes)
    return run


def _set_job_status(job_id: int, status: str, **kwargs) -> None:
    with get_db() as conn:
        sets = ["status = %s"]
        vals: list = [status]
        for col, val in kwargs.items():
            sets.append(f"{col} = %s")
            if col == "plan_json" and isinstance(val, dict):
                val = json.dumps(val)
            vals.append(val)
        vals.append(job_id)
        with conn.cursor() as cur:
            cur.execute(f"UPDATE jobs SET {', '.join(sets)} WHERE id = %s", vals)
        conn.commit()


def _run_job(job: dict) -> None:
    job_id = job["id"]
    logger.info("Worker picking up job %d (angle: %s)", job_id, job["angle"][:60])

    project = None  # guard against unbound reference in except block

    # Load config — fresh per job so per-campaign overrides are thread-safe
    config = load_config()
    if job.get("visual_model") and "visuals" in config.providers:
        config.providers["visuals"].model = job["visual_model"]

    providers = instantiate_providers(config)

    # Resolve brand + projects dir
    brands_dir = Path(config.brands_dir)
    projects_dir = Path(config.projects_dir)
    brand_name = job["brand_name"]
    brand = BrandIdentity.load(brands_dir, brand_name)

    # Merge angle into brief
    brief = dict(job["brief"] or {})
    brief["_angle"] = job["angle"]

    # Check if this job has a prior project to resume
    if job.get("project_id"):
        project_dir = projects_dir / job["project_id"]
        if project_dir.exists():
            project = Project.load(project_dir)
        else:
            project = Project.create(projects_dir, brand_name, job["angle"])
    else:
        project = Project.create(projects_dir, brand_name, job["angle"])
        _set_job_status(job_id, "running", project_id=project.state.project_id, phase="research")

    # Inject target duration so the planning phase can read it from brief.json
    brief["_target_duration"] = job.get("target_duration") or 30

    # Write brief.json for the phase override to read (also used on resume)
    brief_path = project.project_dir / "brief.json"
    brief_path.write_text(json.dumps(brief))

    phase_overrides: dict = {
        "research": _brief_phase(brief),
    }
    if not job.get("auto_approve"):
        phase_overrides["review"] = _web_review_phase

    # Wrap run_pipeline to update phase in DB as each phase starts
    original_mark_running = project.mark_phase_running

    def patched_mark_running(phase_name: str) -> None:
        original_mark_running(phase_name)
        _set_job_status(job_id, "running", phase=phase_name)

    project.mark_phase_running = patched_mark_running  # type: ignore[method-assign]

    try:
        from reelforge.providers.base import PhaseStatus

        plan_json = job.get("plan_json") or {}
        feedback = plan_json.get("_feedback", "")

        if job.get("phase") == "review" and not feedback:
            # User approved — mark review complete so pipeline resumes from script
            project.state.phases["review"].status = PhaseStatus.COMPLETE
            project.state.current_phase = "script"
            project.save_state()
        elif job.get("phase") == "planning" and feedback:
            # User rejected — reset planning phase so it re-runs with feedback context
            project.state.phases["planning"].status = PhaseStatus.PENDING
            project.state.phases["review"].status = PhaseStatus.PENDING
            project.state.current_phase = "planning"
            project.save_state()
            # Inject feedback into brief so LLM knows what to change
            brief["_plan_feedback"] = feedback

        run_pipeline(project, brand, providers, phase_overrides=phase_overrides)
        output_path = str(project.output_path)
        total_cost = 0.0
        for p in (providers.llm, providers.tts, providers.visual, providers.renderer):
            total_cost += getattr(p, "cost_usd", 0.0)
        _set_job_status(job_id, "complete", output_path=output_path, phase="render", cost_usd=round(total_cost, 4))
        logger.info("Job %d complete — output: %s", job_id, output_path)

    except _ReviewPending:
        plan = project.load_plan()
        _set_job_status(
            job_id, "review_pending",
            phase="review",
            plan_json=plan.model_dump(),
        )
        logger.info("Job %d paused for plan review", job_id)
    except Exception as e:
        current_phase = project.state.current_phase if project else None
        _set_job_status(job_id, "failed", error=str(e), phase=current_phase)
        logger.exception("Job %d failed", job_id)
    finally:
        for p in (providers.llm, providers.tts, providers.visual, providers.renderer):
            if hasattr(p, "release"):
                p.release()
            if hasattr(p, "close"):
                p.close()


def _poll_loop() -> None:
    logger.info("Worker poll loop started")
    while True:
        try:
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT j.id, j.angle, j.status, j.phase, j.project_id,
                               j.plan_json, c.brief, c.brand_name, c.auto_approve,
                               c.visual_model, c.target_duration
                        FROM jobs j
                        JOIN campaigns c ON c.id = j.campaign_id
                        WHERE j.status = 'pending'
                        ORDER BY j.created_at
                        LIMIT 1
                        FOR UPDATE SKIP LOCKED
                        """,
                    )
                    row = cur.fetchone()
                    if row:
                        cur.execute(
                            "UPDATE jobs SET status = 'running' WHERE id = %s",
                            (row["id"],),
                        )
                conn.commit()

            if row:
                _run_job(dict(row))

        except Exception:
            logger.exception("Worker poll error")

        time.sleep(_POLL_INTERVAL)


def start_worker() -> None:
    t = threading.Thread(target=_poll_loop, daemon=True, name="reel-forge-worker")
    t.start()
    logger.info("Worker thread started")
