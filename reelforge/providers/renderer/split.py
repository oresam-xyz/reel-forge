"""Split a video into parts that fit within a file size limit (e.g. WhatsApp 10 MB)."""

from __future__ import annotations

import logging
import math
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_MAX_MB = 10


def split_video(
    input_path: str,
    max_size_mb: float = DEFAULT_MAX_MB,
    output_dir: str | None = None,
) -> list[str]:
    """Split a video into parts under max_size_mb each.

    Uses ffprobe to get duration and bitrate, calculates how many parts are
    needed, then uses ffmpeg segment muxer for accurate splitting.

    Args:
        input_path: Path to the source video.
        max_size_mb: Maximum file size per part in megabytes.
        output_dir: Directory for output parts. Defaults to same dir as input.

    Returns:
        List of paths to the split parts.
    """
    input_path = Path(input_path)
    if not input_path.exists():
        raise FileNotFoundError(f"Video not found: {input_path}")

    file_size_mb = input_path.stat().st_size / (1024 * 1024)
    if file_size_mb <= max_size_mb:
        logger.info("Video is %.1f MB, under %.0f MB limit — no split needed", file_size_mb, max_size_mb)
        return [str(input_path)]

    # Get duration via ffprobe
    result = subprocess.run(
        [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_format", str(input_path),
        ],
        capture_output=True, text=True, check=True,
    )
    import json
    fmt = json.loads(result.stdout)["format"]
    duration = float(fmt["duration"])
    bitrate = int(fmt["bit_rate"])

    # Calculate segment duration to stay under max_size_mb
    max_size_bits = max_size_mb * 8 * 1024 * 1024
    # Leave 5% headroom for container overhead
    segment_duration = (max_size_bits * 0.95) / bitrate
    num_parts = math.ceil(duration / segment_duration)

    if output_dir is None:
        output_dir = input_path.parent
    else:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

    stem = input_path.stem
    pattern = str(output_dir / f"{stem}_part%03d.mp4")

    logger.info(
        "Splitting %.1f MB video (%.1fs) into ~%d parts of ~%.0fs each",
        file_size_mb, duration, num_parts, segment_duration,
    )

    subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(input_path),
            "-c", "copy",
            "-f", "segment",
            "-segment_time", str(segment_duration),
            "-reset_timestamps", "1",
            "-movflags", "+faststart",
            pattern,
        ],
        capture_output=True, text=True, check=True,
    )

    # Collect output files
    parts = sorted(output_dir.glob(f"{stem}_part*.mp4"))
    result_paths = [str(p) for p in parts]

    for p in parts:
        size_mb = p.stat().st_size / (1024 * 1024)
        logger.info("  Part: %s (%.1f MB)", p.name, size_mb)

    logger.info("Split complete: %d parts", len(result_paths))
    return result_paths
