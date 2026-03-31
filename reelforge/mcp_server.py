"""ReelForge MCP server — expose video generation pipeline as MCP tools."""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

# Allow local minimcp install
try:
    from minimcp import MiniMCP
except ImportError:
    _minimcp_path = os.environ.get(
        "MINIMCP_PATH",
        str(Path.home() / "Documents" / "projects" / "minimcp"),
    )
    sys.path.insert(0, _minimcp_path)
    from minimcp import MiniMCP

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy-loaded singletons
# ---------------------------------------------------------------------------

_root: Path | None = None
_config = None
_brands_dir: Path | None = None
_projects_dir: Path | None = None
_providers = None


def _get_root() -> Path:
    global _root
    if _root is None:
        _root = Path(os.environ.get("REELFORGE_ROOT", os.getcwd())).resolve()
    return _root


def _get_config():
    global _config, _brands_dir, _projects_dir
    if _config is None:
        from reelforge.config import load_config

        _config = load_config(_get_root() / "config.yaml")
        _brands_dir = Path(_config.brands_dir).resolve()
        _projects_dir = Path(_config.projects_dir).resolve()
        _brands_dir.mkdir(parents=True, exist_ok=True)
        _projects_dir.mkdir(parents=True, exist_ok=True)
    return _config


def _get_dirs() -> tuple[Path, Path]:
    _get_config()
    return _brands_dir, _projects_dir


def _get_providers():
    global _providers
    if _providers is None:
        from reelforge.agent.runner import instantiate_providers

        _providers = instantiate_providers(_get_config())
    return _providers


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _auto_approve_review(project, brand, providers) -> None:
    """Non-interactive review — just approve the plan."""
    plan = project.load_plan()
    plan.approved = True
    project.save_plan(plan)
    logger.info("Plan auto-approved for project %s", project.state.project_id)


def _stop_before_review(project, brand, providers) -> None:
    """Stop the pipeline before review so the agent can inspect the plan."""
    raise _ReviewPending()


class _ReviewPending(Exception):
    """Sentinel exception to halt the pipeline before review."""

    pass


# ---------------------------------------------------------------------------
# MCP server and tools
# ---------------------------------------------------------------------------

mcp = MiniMCP("reelforge")


@mcp.tool()
def create_brand(
    name: str,
    character: str,
    speaks_as: str = "first person, direct and engaging",
    voice: str = "enthusiastic but grounded",
    reading_pace: str = "medium",
    vocabulary: str = "conversational",
    always_does: str = "",
    never_does: str = "",
    aesthetic: str = "modern, clean, dark theme",
    colour_palette: str = "",
    caption_style: str = "word_by_word",
    image_prompt_prefix: str = "",
    tts_provider: str = "kokoro",
    voice_id: str = "af_heart",
    speed: float = 1.0,
    pitch_adjust: float = 0.0,
) -> str:
    """Create a new brand identity for video generation."""
    from reelforge.agent.brand import BrandIdentity
    from reelforge.providers.base import (
        BrandIdentityData,
        Persona,
        Tone,
        VisualStyle,
        VoiceProfile,
    )

    brands_dir, _ = _get_dirs()

    always_list = [s.strip() for s in always_does.split(",") if s.strip()] if always_does else []
    never_list = [s.strip() for s in never_does.split(",") if s.strip()] if never_does else []
    colours = [s.strip() for s in colour_palette.split(",") if s.strip()] if colour_palette else []

    data = BrandIdentityData(
        name=name,
        persona=Persona(
            character=character,
            speaks_as=speaks_as,
            always_does=always_list,
            never_does=never_list,
        ),
        tone=Tone(voice=voice, reading_pace=reading_pace, vocabulary=vocabulary),
        visual_style=VisualStyle(
            aesthetic=aesthetic,
            colour_palette=colours,
            caption_style=caption_style,
            image_prompt_prefix=image_prompt_prefix,
        ),
        voice_profile=VoiceProfile(
            provider=tts_provider,
            voice_id=voice_id,
            speed=speed,
            pitch_adjust=pitch_adjust,
        ),
    )

    brand = BrandIdentity.save(brands_dir, data)
    return json.dumps({"name": name, "path": str(brand.brand_dir)})


@mcp.tool()
def create_project(topic: str, brand: str) -> str:
    """Create a new video project. Returns the project ID. Does not start the pipeline."""
    from reelforge.agent.brand import BrandIdentity
    from reelforge.agent.project import Project

    brands_dir, projects_dir = _get_dirs()

    # Validate brand exists
    BrandIdentity.load(brands_dir, brand)

    project = Project.create(projects_dir, brand, topic)
    return json.dumps({
        "project_id": project.state.project_id,
        "topic": topic,
        "brand": brand,
        "path": str(project.project_dir),
    })


@mcp.tool()
def run_pipeline(project_id: str, auto_approve: bool = True) -> str:
    """Run or resume the video generation pipeline for a project."""
    from reelforge.agent.brand import BrandIdentity
    from reelforge.agent.project import Project
    from reelforge.agent.runner import run_pipeline as _run_pipeline

    brands_dir, projects_dir = _get_dirs()
    providers = _get_providers()

    project = Project.load(projects_dir / project_id)
    brand = BrandIdentity.load(brands_dir, project.state.brand)

    overrides = {}
    if auto_approve:
        overrides["review"] = _auto_approve_review
    else:
        # MCP is non-interactive — never fall through to the CLI review phase.
        # If plan is already approved (via approve_plan), just mark it done.
        # Otherwise, stop before review so the agent can inspect and approve.
        plan_path = project.project_dir / "plan.json"
        if plan_path.exists():
            plan = project.load_plan()
            if plan.approved:
                overrides["review"] = _auto_approve_review
            else:
                overrides["review"] = _stop_before_review
        else:
            overrides["review"] = _stop_before_review

    try:
        _run_pipeline(project, brand, providers, phase_overrides=overrides or None)
    except _ReviewPending:
        return json.dumps({
            "status": "review_pending",
            "project_id": project.state.project_id,
            "message": "Pipeline paused before review. Use get_plan and approve_plan to continue.",
        })

    return json.dumps({
        "status": "complete",
        "project_id": project.state.project_id,
        "output": str(project.output_path),
        "phases": {
            name: info.model_dump()
            for name, info in project.state.phases.items()
        },
    })


@mcp.tool()
def get_project_status(project_id: str) -> str:
    """Get the current status of all phases in a project."""
    from reelforge.agent.project import Project

    _, projects_dir = _get_dirs()
    project = Project.load(projects_dir / project_id)

    return json.dumps({
        "project_id": project.state.project_id,
        "topic": project.state.topic,
        "brand": project.state.brand,
        "current_phase": project.state.current_phase,
        "created_at": project.state.created_at,
        "phases": {
            name: info.model_dump()
            for name, info in project.state.phases.items()
        },
    })


@mcp.tool()
def list_projects() -> str:
    """List all video projects with their current status."""
    from reelforge.agent.project import Project

    _, projects_dir = _get_dirs()
    results = []

    for d in sorted(projects_dir.iterdir()):
        state_path = d / "state.json"
        if not state_path.exists():
            continue
        try:
            project = Project.load(d)
            s = project.state
            results.append({
                "project_id": s.project_id,
                "topic": s.topic,
                "brand": s.brand,
                "current_phase": s.current_phase,
                "created_at": s.created_at,
                "has_output": project.output_path.exists(),
            })
        except Exception as e:
            results.append({"project_id": d.name, "error": str(e)})

    return json.dumps(results)


@mcp.tool()
def list_brands() -> str:
    """List all available brand identities."""
    from reelforge.agent.brand import BrandIdentity

    brands_dir, _ = _get_dirs()
    brands = BrandIdentity.list_brands(brands_dir)
    return json.dumps([{"name": name, "character": character} for name, character in brands])


@mcp.tool()
def get_plan(project_id: str) -> str:
    """Get the content plan for a project, for review before approval."""
    from reelforge.agent.project import Project

    _, projects_dir = _get_dirs()
    project = Project.load(projects_dir / project_id)
    plan = project.load_plan()

    return json.dumps({
        "project_id": project_id,
        "approved": plan.approved,
        "edit_rounds": plan.edit_rounds,
        "hook": plan.hook,
        "segments": [
            {
                "narration": seg.narration,
                "visual_brief": seg.visual_brief,
                "duration_seconds": seg.duration_seconds,
            }
            for seg in plan.segments
        ],
        "cta": plan.cta,
        "tone_guidance": plan.tone_guidance,
        "estimated_duration_seconds": plan.estimated_duration_seconds,
    })


@mcp.tool()
def approve_plan(project_id: str, approved: bool, feedback: str = "") -> str:
    """Approve, edit, or reject a project's content plan."""
    from reelforge.agent.phases.review import EDIT_PROMPT
    from reelforge.agent.project import Project
    from reelforge.providers.base import PhaseStatus, Segment

    brands_dir, projects_dir = _get_dirs()
    project = Project.load(projects_dir / project_id)
    plan = project.load_plan()

    if approved and not feedback:
        # Straight approval
        plan.approved = True
        project.save_plan(plan)
        # Mark review phase complete so run_pipeline continues from script
        project.mark_phase_complete("review")
        return json.dumps({"status": "approved", "project_id": project_id})

    if approved and feedback:
        # Approve with edits — apply feedback via LLM first, then approve
        from reelforge.agent.brand import BrandIdentity

        brand = BrandIdentity.load(brands_dir, project.state.brand)
        providers = _get_providers()

        edit_prompt = EDIT_PROMPT.format(
            plan_json=plan.model_dump_json(indent=2),
            always_does=", ".join(brand.data.persona.always_does) or "(none)",
            never_does=", ".join(brand.data.persona.never_does) or "(none)",
            user_feedback=feedback,
        )
        updated_data = providers.llm.generate_json(edit_prompt, system=brand.system_prompt)

        segments = []
        for seg in updated_data.get("segments", []):
            segments.append(Segment(
                narration=seg.get("narration", ""),
                visual_brief=seg.get("visual_brief", ""),
                duration_seconds=seg.get("duration_seconds", 5),
            ))

        from reelforge.providers.base import ContentPlan

        plan = ContentPlan(
            hook=updated_data.get("hook", plan.hook),
            segments=segments if segments else plan.segments,
            cta=updated_data.get("cta", plan.cta),
            tone_guidance=updated_data.get("tone_guidance", plan.tone_guidance),
            estimated_duration_seconds=updated_data.get(
                "estimated_duration_seconds", plan.estimated_duration_seconds
            ),
            approved=True,
            edit_rounds=plan.edit_rounds + 1,
        )
        project.save_plan(plan)
        project.mark_phase_complete("review")
        return json.dumps({"status": "approved_with_edits", "project_id": project_id})

    if not approved and feedback:
        # Reject with feedback — apply edits but don't approve
        from reelforge.agent.brand import BrandIdentity

        brand = BrandIdentity.load(brands_dir, project.state.brand)
        providers = _get_providers()

        edit_prompt = EDIT_PROMPT.format(
            plan_json=plan.model_dump_json(indent=2),
            always_does=", ".join(brand.data.persona.always_does) or "(none)",
            never_does=", ".join(brand.data.persona.never_does) or "(none)",
            user_feedback=feedback,
        )
        updated_data = providers.llm.generate_json(edit_prompt, system=brand.system_prompt)

        segments = []
        for seg in updated_data.get("segments", []):
            segments.append(Segment(
                narration=seg.get("narration", ""),
                visual_brief=seg.get("visual_brief", ""),
                duration_seconds=seg.get("duration_seconds", 5),
            ))

        from reelforge.providers.base import ContentPlan

        plan = ContentPlan(
            hook=updated_data.get("hook", plan.hook),
            segments=segments if segments else plan.segments,
            cta=updated_data.get("cta", plan.cta),
            tone_guidance=updated_data.get("tone_guidance", plan.tone_guidance),
            estimated_duration_seconds=updated_data.get(
                "estimated_duration_seconds", plan.estimated_duration_seconds
            ),
            approved=False,
            edit_rounds=plan.edit_rounds + 1,
        )
        project.save_plan(plan)
        return json.dumps({"status": "edited", "project_id": project_id})

    # Reject without feedback — reset planning phase
    project.state.phases["planning"].status = PhaseStatus.PENDING
    project.state.phases["planning"].completed_at = None
    project.state.phases["planning"].error = None
    project.state.phases["review"].status = PhaseStatus.PENDING
    project.state.phases["review"].completed_at = None
    project.state.phases["review"].error = None
    project.state.current_phase = "planning"
    project.save_state()
    return json.dumps({
        "status": "regenerate",
        "project_id": project_id,
        "message": "Planning reset. Call run_pipeline to regenerate the plan.",
    })


@mcp.tool()
def reset_phases(project_id: str, from_phase: str) -> str:
    """Reset a project's pipeline from a given phase onward so it can be re-run.

    All phases from `from_phase` to the end are set back to pending.
    Use this before run_pipeline to reproduce assets, re-render, regenerate the
    plan, etc.

    Valid phase names: research, planning, review, script, assets, render.
    """
    from reelforge.agent.project import PHASES, Project
    from reelforge.providers.base import PhaseStatus

    _, projects_dir = _get_dirs()
    project = Project.load(projects_dir / project_id)

    if from_phase not in PHASES:
        return json.dumps({"error": f"Unknown phase '{from_phase}'. Valid: {PHASES}"})

    start_idx = PHASES.index(from_phase)
    reset = []
    for phase_name in PHASES[start_idx:]:
        project.state.phases[phase_name].status = PhaseStatus.PENDING
        project.state.phases[phase_name].completed_at = None
        project.state.phases[phase_name].error = None
        reset.append(phase_name)

    project.state.current_phase = from_phase
    project.save_state()

    return json.dumps({
        "status": "reset",
        "project_id": project_id,
        "from_phase": from_phase,
        "reset_phases": reset,
        "message": f"Phases reset. Call run_pipeline to continue from '{from_phase}'.",
    })


@mcp.tool()
def get_script(project_id: str) -> str:
    """Get the generated script for a project. Available after the script phase completes."""
    from reelforge.agent.project import Project

    _, projects_dir = _get_dirs()
    project = Project.load(projects_dir / project_id)

    script = project.load_script()
    return json.dumps({
        "project_id": project_id,
        "title": script.title,
        "segments": [
            {
                "segment_id": seg.segment_id,
                "narration": seg.narration,
                "visual_prompt": seg.visual_prompt,
                "duration_seconds": seg.duration_seconds,
            }
            for seg in script.segments
        ],
        "total_duration": script.total_duration,
    })


@mcp.tool()
def update_script(
    project_id: str,
    segment_id: int = -1,
    narration: str = "",
    visual_prompt: str = "",
    duration_seconds: float = 0,
    title: str = "",
) -> str:
    """Update a specific segment in the script, or the title.

    Pass segment_id to update a segment. Only provided fields are changed.
    Pass title to update the script title.
    After updating, use reset_phases(from_phase="assets") then run_pipeline
    to regenerate the video with the new script.
    """
    from reelforge.agent.project import Project

    _, projects_dir = _get_dirs()
    project = Project.load(projects_dir / project_id)
    script = project.load_script()

    if title:
        script.title = title

    if segment_id >= 0:
        if segment_id >= len(script.segments):
            return json.dumps({
                "error": f"segment_id {segment_id} out of range (0-{len(script.segments) - 1})"
            })

        seg = script.segments[segment_id]
        if narration:
            seg.narration = narration
        if visual_prompt:
            seg.visual_prompt = visual_prompt
        if duration_seconds > 0:
            seg.duration_seconds = duration_seconds

        # Recalculate total duration
        script.total_duration = sum(s.duration_seconds for s in script.segments)

    project.save_script(script)

    return json.dumps({
        "status": "updated",
        "project_id": project_id,
        "title": script.title,
        "segments": [
            {
                "segment_id": seg.segment_id,
                "narration": seg.narration,
                "visual_prompt": seg.visual_prompt,
                "duration_seconds": seg.duration_seconds,
            }
            for seg in script.segments
        ],
        "total_duration": script.total_duration,
    })


if __name__ == "__main__":
    mcp.run()
