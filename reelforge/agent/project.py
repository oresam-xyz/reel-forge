"""Project class — single gateway for all project state and file I/O."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from reelforge.providers.base import (
    CaptionData,
    ContentPlan,
    PhaseInfo,
    PhaseStatus,
    ProjectState,
    ResearchNotes,
    Script,
)

logger = logging.getLogger(__name__)

PHASES = ["research", "planning", "review", "script", "assets", "render"]


def _slugify(text: str) -> str:
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    return slug[:50].strip("-")


class Project:
    """Manages a single video project's state and artefact files."""

    def __init__(self, project_dir: Path, state: ProjectState) -> None:
        self.project_dir = project_dir
        self.state = state

    # ------------------------------------------------------------------
    # Factory methods
    # ------------------------------------------------------------------

    @classmethod
    def create(cls, base_dir: Path, brand_name: str, topic: str) -> Project:
        """Create a new project with fresh state."""
        now = datetime.now(timezone.utc)
        project_id = f"{now.strftime('%Y-%m-%d')}_{_slugify(topic)}"
        project_dir = base_dir / project_id

        # Handle duplicate IDs
        counter = 1
        while project_dir.exists():
            project_id = f"{now.strftime('%Y-%m-%d')}_{_slugify(topic)}_{counter}"
            project_dir = base_dir / project_id
            counter += 1

        project_dir.mkdir(parents=True)
        (project_dir / "assets").mkdir()

        phases = {name: PhaseInfo() for name in PHASES}

        state = ProjectState(
            project_id=project_id,
            brand=brand_name,
            topic=topic,
            created_at=now.isoformat(),
            phases=phases,
            current_phase="research",
        )

        project = cls(project_dir, state)
        project.save_state()
        logger.info("Created project %s at %s", project_id, project_dir)
        return project

    @classmethod
    def load(cls, project_dir: Path) -> Project:
        """Load an existing project from its directory."""
        state_path = project_dir / "state.json"
        if not state_path.exists():
            raise FileNotFoundError(f"No state.json found in {project_dir}")
        raw = json.loads(state_path.read_text())
        state = ProjectState.model_validate(raw)
        logger.info("Loaded project %s", state.project_id)
        return cls(project_dir, state)

    # ------------------------------------------------------------------
    # State management
    # ------------------------------------------------------------------

    def save_state(self) -> None:
        path = self.project_dir / "state.json"
        path.write_text(self.state.model_dump_json(indent=2))

    def mark_phase_running(self, phase_name: str) -> None:
        self.state.phases[phase_name].status = PhaseStatus.PENDING  # still pending until done
        self.state.current_phase = phase_name
        self.save_state()

    def mark_phase_complete(self, phase_name: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self.state.phases[phase_name].status = PhaseStatus.COMPLETE
        self.state.phases[phase_name].completed_at = now
        self.state.phases[phase_name].error = None
        self._advance_current_phase(phase_name)
        self.save_state()
        logger.info("Phase '%s' completed", phase_name)

    def mark_phase_failed(self, phase_name: str, error: str) -> None:
        self.state.phases[phase_name].status = PhaseStatus.FAILED
        self.state.phases[phase_name].error = error
        self.save_state()
        logger.error("Phase '%s' failed: %s", phase_name, error)

    def _advance_current_phase(self, completed_phase: str) -> None:
        try:
            idx = PHASES.index(completed_phase)
            if idx + 1 < len(PHASES):
                self.state.current_phase = PHASES[idx + 1]
        except ValueError:
            pass

    def get_current_phase(self) -> str:
        return self.state.current_phase

    # ------------------------------------------------------------------
    # Regeneration notes
    # ------------------------------------------------------------------

    def set_regeneration_notes(self, notes: str) -> None:
        self.state.regeneration_notes = notes
        self.save_state()

    def clear_regeneration_notes(self) -> None:
        self.state.regeneration_notes = ""
        self.save_state()

    # ------------------------------------------------------------------
    # Artefact I/O — research
    # ------------------------------------------------------------------

    def save_research(self, notes: ResearchNotes) -> None:
        path = self.project_dir / "research.json"
        path.write_text(notes.model_dump_json(indent=2))

    def load_research(self) -> ResearchNotes:
        path = self.project_dir / "research.json"
        return ResearchNotes.model_validate_json(path.read_text())

    # ------------------------------------------------------------------
    # Artefact I/O — plan
    # ------------------------------------------------------------------

    def save_plan(self, plan: ContentPlan) -> None:
        path = self.project_dir / "plan.json"
        path.write_text(plan.model_dump_json(indent=2))

    def load_plan(self) -> ContentPlan:
        path = self.project_dir / "plan.json"
        return ContentPlan.model_validate_json(path.read_text())

    # ------------------------------------------------------------------
    # Artefact I/O — script
    # ------------------------------------------------------------------

    def save_script(self, script: Script) -> None:
        path = self.project_dir / "assets" / "script.json"
        path.write_text(script.model_dump_json(indent=2))

    def load_script(self) -> Script:
        path = self.project_dir / "assets" / "script.json"
        return Script.model_validate_json(path.read_text())

    # ------------------------------------------------------------------
    # Artefact I/O — captions
    # ------------------------------------------------------------------

    def save_captions(self, captions: CaptionData) -> None:
        path = self.project_dir / "assets" / "captions.json"
        path.write_text(captions.model_dump_json(indent=2))

    def load_captions(self) -> CaptionData:
        path = self.project_dir / "assets" / "captions.json"
        return CaptionData.model_validate_json(path.read_text())

    # ------------------------------------------------------------------
    # Path helpers
    # ------------------------------------------------------------------

    @property
    def assets_dir(self) -> Path:
        return self.project_dir / "assets"

    @property
    def output_path(self) -> Path:
        return self.project_dir / "output.mp4"

    def asset_path(self, filename: str) -> Path:
        return self.assets_dir / filename
