"""Phase 3: Human-in-the-loop review — display plan, collect approval/edits."""

from __future__ import annotations

import logging
import sys

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from reelforge.agent.brand import BrandIdentity
from reelforge.agent.project import Project
from reelforge.providers.base import ContentPlan, PhaseStatus, Providers, Segment

logger = logging.getLogger(__name__)

EDIT_PROMPT = """\
You are editing a content plan for a short-form video based on user feedback.

Current plan:
{plan_json}

Brand constraints:
Always do: {always_does}
Never do: {never_does}

User's requested changes:
{user_feedback}

Apply ONLY the changes the user requested. Keep everything else the same. \
If any requested change conflicts with the brand constraints listed above, \
note the conflict in the tone_guidance field and do NOT apply that specific change.

Return the updated plan as a JSON object with the same structure:
{{
  "hook": "...",
  "segments": [{{"narration": "...", "visual_brief": "...", "duration_seconds": N}}],
  "cta": "...",
  "tone_guidance": "...",
  "estimated_duration_seconds": N
}}
"""

MAX_EDIT_ROUNDS = 3


def _display_plan(console: Console, plan: ContentPlan) -> None:
    """Display the content plan in a readable format."""
    console.print()
    console.print(Panel(f"[bold cyan]{plan.hook}[/]", title="Hook", border_style="cyan"))

    table = Table(title="Segments", show_lines=True)
    table.add_column("#", style="dim", width=3)
    table.add_column("Narration", ratio=2)
    table.add_column("Visual Brief", ratio=2)
    table.add_column("Duration", width=8, justify="center")

    for i, seg in enumerate(plan.segments, 1):
        table.add_row(str(i), seg.narration, seg.visual_brief, f"{seg.duration_seconds}s")

    console.print(table)
    console.print(Panel(f"[bold green]{plan.cta}[/]", title="Call to Action", border_style="green"))

    if plan.tone_guidance:
        console.print(f"\n[dim]Tone guidance:[/] {plan.tone_guidance}")
    console.print(f"[dim]Estimated duration:[/] {plan.estimated_duration_seconds}s")
    console.print()


def run(project: Project, brand: BrandIdentity, providers: Providers) -> None:
    """Execute the review phase — interactive CLI loop."""
    console = Console()
    plan = project.load_plan()

    while True:
        _display_plan(console, plan)

        console.print("[bold]What would you like to do?[/]")
        console.print("  [A] Approve this plan")
        console.print("  [B] Edit — request specific changes")
        console.print("  [C] Regenerate — start planning from scratch")
        console.print("  [D] Cancel this project")

        if plan.edit_rounds >= MAX_EDIT_ROUNDS:
            console.print(
                f"\n[yellow]You've made {plan.edit_rounds} edit rounds. "
                f"Consider [C] Regenerate for a fresh plan.[/]"
            )

        choice = Prompt.ask(
            "Choice",
            choices=["A", "B", "C", "D", "a", "b", "c", "d"],
            show_choices=False,
        ).upper()

        if choice == "A":
            plan.approved = True
            project.save_plan(plan)
            console.print("[bold green]Plan approved![/]")
            logger.info("Plan approved after %d edit rounds", plan.edit_rounds)
            return

        elif choice == "B":
            user_feedback = Prompt.ask("Describe the changes you want")
            if not user_feedback.strip():
                console.print("[yellow]No changes provided, try again.[/]")
                continue

            # Check for conflicts with brand constraints
            console.print("[dim]Applying edits via LLM...[/]")
            edit_prompt = EDIT_PROMPT.format(
                plan_json=plan.model_dump_json(indent=2),
                always_does=", ".join(brand.data.persona.always_does) or "(none)",
                never_does=", ".join(brand.data.persona.never_does) or "(none)",
                user_feedback=user_feedback,
            )

            updated_data = providers.llm.generate_json(
                edit_prompt, system=brand.system_prompt
            )

            # Rebuild plan from LLM output
            segments = []
            for seg in updated_data.get("segments", []):
                segments.append(Segment(
                    narration=seg.get("narration", ""),
                    visual_brief=seg.get("visual_brief", ""),
                    duration_seconds=seg.get("duration_seconds", 5),
                ))

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

            # Check if tone_guidance mentions a conflict
            tg = plan.tone_guidance.lower()
            if "conflict" in tg or "constraint" in tg:
                console.print(
                    f"[yellow]Note from LLM:[/] {plan.tone_guidance}"
                )

            console.print("[green]Plan updated. Showing revised version:[/]")

        elif choice == "C":
            reason = Prompt.ask("Why should we regenerate? (brief reason)")
            project.set_regeneration_notes(reason)
            # Reset planning phase to pending so runner re-runs it
            project.state.phases["planning"].status = PhaseStatus.PENDING
            project.state.phases["planning"].completed_at = None
            project.state.phases["planning"].error = None
            project.state.current_phase = "planning"
            project.save_state()
            console.print(
                "[yellow]Planning phase reset. Re-run the pipeline to regenerate.[/]"
            )
            logger.info("Plan regeneration requested: %s", reason)
            sys.exit(0)

        elif choice == "D":
            console.print("[red]Project cancelled.[/]")
            # Mark all remaining phases as failed
            for phase_name, info in project.state.phases.items():
                if info.status != PhaseStatus.COMPLETE:
                    info.status = PhaseStatus.FAILED
                    info.error = "Project cancelled by user"
            project.save_state()
            logger.info("Project cancelled by user")
            sys.exit(0)
