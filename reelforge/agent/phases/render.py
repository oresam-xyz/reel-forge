"""Phase 6: FFmpeg composite — images + audio + word-by-word captions."""

from __future__ import annotations

import logging

from reelforge.agent.brand import BrandIdentity
from reelforge.agent.project import Project
from reelforge.providers.base import AudioAsset, CaptionData, Providers, VisualAsset

logger = logging.getLogger(__name__)

WHISPER_MODEL = "base"


def _generate_captions(audio_path: str) -> CaptionData:
    """Use OpenAI Whisper to generate word-level timestamps from audio."""
    try:
        import whisper
    except ImportError:
        raise ImportError(
            "The 'openai-whisper' package is required for caption generation. "
            "Install it with: pip install openai-whisper"
        )
    from reelforge.providers.base import WordTimestamp

    logger.info("Transcribing audio for captions using Whisper (%s model)", WHISPER_MODEL)
    model = whisper.load_model(WHISPER_MODEL)
    result = model.transcribe(audio_path, word_timestamps=True)

    words = []
    for segment in result.get("segments", []):
        for word_info in segment.get("words", []):
            words.append(WordTimestamp(
                word=word_info.get("word", "").strip(),
                start=word_info.get("start", 0.0),
                end=word_info.get("end", 0.0),
            ))

    logger.info("Generated %d word-level timestamps", len(words))
    return CaptionData(words=words)


def _generate_captions_from_script(project: Project) -> CaptionData:
    """Fallback: distribute words evenly across segment durations when Whisper is unavailable."""
    from reelforge.providers.base import WordTimestamp

    script = project.load_script()
    words = []
    time_offset = 0.0
    for seg in script.segments:
        seg_words = seg.narration.split()
        if not seg_words:
            time_offset += seg.duration_seconds
            continue
        word_duration = seg.duration_seconds / len(seg_words)
        for i, word in enumerate(seg_words):
            start = time_offset + i * word_duration
            words.append(WordTimestamp(word=word, start=start, end=start + word_duration))
        time_offset += seg.duration_seconds

    logger.info("Generated %d script-based word timestamps (no Whisper)", len(words))
    return CaptionData(words=words)


def _collect_visual_assets(project: Project) -> list[VisualAsset]:
    """Collect all visual assets (video clips or images) from the project's assets directory."""
    assets_dir = project.assets_dir

    # Check for video clips first, fall back to images
    clips = sorted(assets_dir.glob("clip_*.mp4"))
    if clips:
        return [
            VisualAsset(path=str(p), segment_id=i, type="video")
            for i, p in enumerate(clips)
        ]

    images = sorted(assets_dir.glob("img_*.png"))
    return [
        VisualAsset(path=str(p), segment_id=i, type="image")
        for i, p in enumerate(images)
    ]


def run(project: Project, brand: BrandIdentity, providers: Providers) -> None:
    """Execute the render phase."""
    script = project.load_script()
    audio_path = str(project.asset_path("audio.wav"))

    # Generate word-level captions — prefer Whisper, fall back to script-based timing
    try:
        captions = _generate_captions(audio_path)
    except ImportError:
        logger.warning("Whisper not available — falling back to script-based caption timing")
        captions = _generate_captions_from_script(project)

    # Reverse brand pronunciation substitutions so captions show display text
    if brand.data.pronunciations:
        # Build a reverse map: spoken → display, normalised to lowercase for matching
        reverse = {spoken.lower(): display for display, spoken in brand.data.pronunciations.items()}
        for word in captions.words:
            w = word.word.strip().lower()
            if w in reverse:
                word.word = word.word.replace(w, reverse[w]).replace(w.capitalize(), reverse[w])

    project.save_captions(captions)

    # Collect visual assets
    visuals = _collect_visual_assets(project)
    if not visuals:
        raise RuntimeError("No visual assets found in project assets directory")

    audio_asset = AudioAsset(path=audio_path)

    # Build render config from brand visual style
    render_config = {
        "resolution": "1080x1920",
        "format": "9x16",
        "colour_palette": brand.data.visual_style.colour_palette,
        "caption_style": brand.data.visual_style.caption_style,
    }

    logger.info(
        "Rendering video: %d visuals, audio=%s, %d caption words",
        len(visuals),
        audio_path,
        len(captions.words),
    )

    output_path = providers.renderer.render(
        script=script,
        audio=audio_asset,
        visuals=visuals,
        captions=captions,
        config=render_config,
    )

    # Move/copy output to project output path if not already there
    from pathlib import Path
    import shutil

    final_path = project.output_path
    tmpdir = Path(output_path).parent
    if Path(output_path) != final_path:
        shutil.move(output_path, final_path)
    shutil.rmtree(tmpdir, ignore_errors=True)

    logger.info("Video rendered: %s", final_path)

    # Compress with H.265 via PyAV
    try:
        from reelforge.providers.renderer.compress import compress_video
        compress_video(str(final_path))
    except ImportError:
        logger.warning("PyAV not installed — skipping H.265 compression (pip install av)")
    except Exception as e:
        logger.warning("Compression failed, keeping original: %s", e)
