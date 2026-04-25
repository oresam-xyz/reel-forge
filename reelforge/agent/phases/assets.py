"""Phase 5: Asset generation — voice first, then visuals (both need GPU)."""

from __future__ import annotations

import logging

from reelforge.agent.brand import BrandIdentity
from reelforge.agent.project import Project
from reelforge.providers.base import Providers, SegmentBrief

logger = logging.getLogger(__name__)


def _generate_voice(project: Project, brand: BrandIdentity, providers: Providers) -> str:
    """Generate the full narration audio as a single WAV file."""
    audio_path = project.asset_path("audio.wav")

    # Skip if already generated (resuming after partial failure)
    if audio_path.exists() and audio_path.stat().st_size > 0:
        logger.info("Audio already exists, skipping TTS: %s", audio_path)
        return str(audio_path)

    script = project.load_script()
    full_narration = " ".join(seg.narration for seg in script.segments)

    # Apply brand pronunciation substitutions (display text → spoken text for TTS)
    tts_text = full_narration
    for display, spoken in brand.data.pronunciations.items():
        tts_text = tts_text.replace(display, spoken)

    voice_profile = brand.data.voice_profile.model_dump()
    voice_profile["output_path"] = str(audio_path)

    logger.info("Generating voice audio (%d characters)", len(tts_text))
    audio_asset = providers.tts.synthesise(tts_text, voice_profile)
    logger.info("Voice audio saved: %s", audio_asset.path)
    return audio_asset.path


def _generate_visuals(project: Project, brand: BrandIdentity, providers: Providers) -> list[str]:
    """Generate one image per segment."""
    script = project.load_script()
    style = brand.data.visual_style.model_dump()
    prefix = brand.data.visual_style.image_prompt_prefix

    briefs = []
    for seg in script.segments:
        visual_brief = seg.visual_prompt
        if prefix and not visual_brief.startswith(prefix):
            visual_brief = f"{prefix} {visual_brief}"
        briefs.append(SegmentBrief(
            segment_id=seg.segment_id,
            visual_brief=visual_brief,
            duration_seconds=seg.duration_seconds,
        ))

    style["output_dir"] = str(project.assets_dir)
    logger.info("Generating visuals for %d segments", len(briefs))
    visual_assets = providers.visual.get_visuals(briefs, style)

    paths = []
    for asset in visual_assets:
        logger.info("Visual saved: %s (segment %d)", asset.path, asset.segment_id)
        paths.append(asset.path)

    return paths


def run(project: Project, brand: BrandIdentity, providers: Providers) -> None:
    """Execute the asset generation phase — voice first, then visuals."""
    logger.info("Starting asset generation")

    # Run TTS first, then visuals — both need GPU, can't run in parallel
    audio_path = _generate_voice(project, brand, providers)

    # Free GPU memory from TTS before loading the visual model
    if hasattr(providers.tts, 'release'):
        providers.tts.release()

    visual_paths = _generate_visuals(project, brand, providers)

    # Free GPU memory from visuals before render phase (Whisper needs GPU)
    if hasattr(providers.visual, 'release'):
        providers.visual.release()

    if audio_path is None or visual_paths is None:
        raise RuntimeError("Asset generation incomplete — missing audio or visuals")

    logger.info(
        "All assets generated: audio=%s, %d visuals",
        audio_path,
        len(visual_paths) if visual_paths else 0,
    )
