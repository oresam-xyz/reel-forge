"""Phase 4: Script generation — convert approved plan into full narration script."""

from __future__ import annotations

import logging

from reelforge.agent.brand import BrandIdentity
from reelforge.agent.project import Project
from reelforge.providers.base import Providers, Script, ScriptSegment

logger = logging.getLogger(__name__)

SCRIPT_PROMPT = """\
You are writing the full narration script for a short-form video (reel/short).

Brand identity:
{brand_system_prompt}

Approved content plan:
Hook: {hook}
Segments:
{segments_text}
CTA: {cta}
Tone guidance: {tone_guidance}

Instructions:
- Write the narration for each segment in the brand's voice and tone.
- The narration should sound natural when spoken aloud.
- Match the reading pace: {reading_pace}
- Vocabulary level: {vocabulary}
- Each segment's narration should flow naturally into the next.
- Generate a visual prompt for each segment that an image generator can use. \
  Prefix each visual prompt with: {image_prompt_prefix}
- Keep to approximately {target_duration} seconds total.

Return a JSON object:
{{
  "title": "video title",
  "segments": [
    {{
      "segment_id": 0,
      "narration": "full narration text for this segment",
      "visual_prompt": "detailed image generation prompt",
      "duration_seconds": 8.0
    }}
  ],
  "total_duration": 60.0
}}
"""


def run(project: Project, brand: BrandIdentity, providers: Providers) -> None:
    """Execute the script generation phase."""
    plan = project.load_plan()
    llm = providers.llm

    # Format segments for the prompt
    segments_text = ""
    for i, seg in enumerate(plan.segments, 1):
        segments_text += (
            f"  {i}. Narration hint: {seg.narration}\n"
            f"     Visual brief: {seg.visual_brief}\n"
            f"     Duration: {seg.duration_seconds}s\n\n"
        )

    prompt = SCRIPT_PROMPT.format(
        brand_system_prompt=brand.system_prompt,
        hook=plan.hook,
        segments_text=segments_text,
        cta=plan.cta,
        tone_guidance=plan.tone_guidance,
        reading_pace=brand.data.tone.reading_pace,
        vocabulary=brand.data.tone.vocabulary,
        image_prompt_prefix=brand.data.visual_style.image_prompt_prefix or "",
        target_duration=plan.estimated_duration_seconds,
    )

    logger.info("Generating script from approved plan")
    script_data = llm.generate_json(prompt, system=brand.system_prompt)

    # Parse response
    segments = []
    for seg in script_data.get("segments", []):
        segments.append(ScriptSegment(
            segment_id=seg.get("segment_id", len(segments)),
            narration=seg.get("narration", ""),
            visual_prompt=seg.get("visual_prompt", ""),
            duration_seconds=seg.get("duration_seconds", 5.0),
        ))

    script = Script(
        title=script_data.get("title", project.state.topic),
        segments=segments,
        total_duration=script_data.get("total_duration", sum(s.duration_seconds for s in segments)),
    )

    project.save_script(script)
    logger.info(
        "Script generated: '%s' — %d segments, %.1fs total",
        script.title,
        len(script.segments),
        script.total_duration,
    )
