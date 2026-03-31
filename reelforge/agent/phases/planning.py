"""Phase 2: Content plan generation — create a structured plan from research notes."""

from __future__ import annotations

import logging

from reelforge.agent.brand import BrandIdentity
from reelforge.agent.project import Project
from reelforge.providers.base import ContentPlan, Providers, Segment

logger = logging.getLogger(__name__)

PLANNING_PROMPT = """\
You are creating a content plan for a short-form video (reel/short).

Topic: {topic}

Brand identity:
{brand_system_prompt}

Research findings:
{key_facts}

{regeneration_section}

Create a compelling content plan. The video should be approximately {target_duration} \
seconds long. Structure it with:
- A strong hook (the opening line/visual that grabs attention in the first 2 seconds)
- Multiple segments, each with narration text and a visual brief (describing what the \
  viewer should see)
- A clear call to action (CTA)
- Tone guidance that matches the brand identity

The plan MUST respect these brand constraints:
Always do: {always_does}
Never do: {never_does}

Return a JSON object with this exact structure:
{{
  "hook": "opening hook text",
  "segments": [
    {{
      "narration": "what the narrator says",
      "visual_brief": "description of the visual for this segment",
      "duration_seconds": 8
    }}
  ],
  "cta": "call to action text",
  "tone_guidance": "guidance for tone and delivery",
  "estimated_duration_seconds": 60
}}
"""


def run(project: Project, brand: BrandIdentity, providers: Providers) -> None:
    """Execute the planning phase."""
    llm = providers.llm

    # Load research
    research = project.load_research()
    key_facts_text = "\n".join(f"- {f}" for f in research.key_facts) or "(no research available)"

    # Build regeneration section if applicable
    regen_notes = project.state.regeneration_notes
    regeneration_section = ""
    if regen_notes:
        regeneration_section = (
            f"IMPORTANT — The previous plan was rejected. The user's feedback:\n"
            f"{regen_notes}\n\n"
            f"Address this feedback in the new plan."
        )

    prompt = PLANNING_PROMPT.format(
        topic=project.state.topic,
        brand_system_prompt=brand.system_prompt,
        key_facts=key_facts_text,
        regeneration_section=regeneration_section,
        target_duration=60,
        always_does=", ".join(brand.data.persona.always_does) or "(none)",
        never_does=", ".join(brand.data.persona.never_does) or "(none)",
    )

    logger.info("Generating content plan")
    plan_data = llm.generate_json(prompt, system=brand.system_prompt)

    # Parse segments
    segments = []
    for seg in plan_data.get("segments", []):
        segments.append(Segment(
            narration=seg.get("narration", ""),
            visual_brief=seg.get("visual_brief", ""),
            duration_seconds=seg.get("duration_seconds", 5),
        ))

    plan = ContentPlan(
        hook=plan_data.get("hook", ""),
        segments=segments,
        cta=plan_data.get("cta", ""),
        tone_guidance=plan_data.get("tone_guidance", ""),
        estimated_duration_seconds=plan_data.get("estimated_duration_seconds", 60),
        approved=False,
        edit_rounds=0,
    )

    project.save_plan(plan)
    # Clear regeneration notes after successful planning
    if regen_notes:
        project.clear_regeneration_notes()

    logger.info(
        "Content plan generated: %d segments, ~%ds total",
        len(plan.segments),
        plan.estimated_duration_seconds,
    )
