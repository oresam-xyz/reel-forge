"""FFmpeg renderer — composite images + audio + captions into final video."""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

from reelforge.providers.base import (
    AudioAsset,
    CaptionData,
    RendererProvider,
    Script,
    VisualAsset,
)

logger = logging.getLogger(__name__)


def _get_audio_duration(ffprobe_path: str, audio_path: str) -> float:
    """Get the duration of an audio file using ffprobe."""
    cmd = [
        ffprobe_path, "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        audio_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        data = json.loads(result.stdout)
        return float(data.get("format", {}).get("duration", 0))
    return 0.0


def _escape_drawtext(text: str) -> str:
    """Escape special characters for FFmpeg drawtext filter."""
    text = text.replace("\\", "\\\\")
    text = text.replace("'", "'\\''")
    text = text.replace(":", "\\:")
    text = text.replace("%", "%%")
    return text


class FFmpegRenderer(RendererProvider):
    """Renderer using FFmpeg for video compositing."""

    def __init__(
        self,
        ffmpeg_path: str = "ffmpeg",
        resolution: str = "1080x1920",
        fps: int = 30,
        **kwargs,
    ) -> None:
        self.ffmpeg_path = ffmpeg_path
        self.resolution = resolution
        self.fps = fps
        # Verify FFmpeg is available
        if not shutil.which(ffmpeg_path):
            logger.warning("FFmpeg not found at '%s'", ffmpeg_path)

    def _build_segment_video(
        self,
        image_path: str,
        duration: float,
        output_path: str,
        width: int,
        height: int,
    ) -> None:
        """Create a video clip from a still image with Ken Burns effect."""
        # Ken Burns: slow zoom from 100% to 110% over the segment duration
        # zoompan filter: zoom from 1.0 to 1.1, pan slightly
        total_frames = int(duration * self.fps)
        zoom_expr = f"min(zoom+0.001,1.1)"
        x_expr = f"iw/2-(iw/zoom/2)"
        y_expr = f"ih/2-(ih/zoom/2)"

        # Scale to 110% of target to give zoom headroom, keeping memory manageable
        zoom_width = int(width * 1.1)
        zoom_height = int(height * 1.1)
        cmd = [
            self.ffmpeg_path, "-y",
            "-loop", "1",
            "-i", image_path,
            "-vf", (
                f"scale={zoom_width}:{zoom_height}:force_original_aspect_ratio=increase,"
                f"crop={zoom_width}:{zoom_height},"
                f"zoompan=z='{zoom_expr}':x='{x_expr}':y='{y_expr}'"
                f":d={total_frames}:s={width}x{height}:fps={self.fps},"
                f"format=yuv420p"
            ),
            "-t", str(duration),
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "26",
            "-pix_fmt", "yuv420p",
            output_path,
        ]

        logger.debug("Running: %s", " ".join(cmd))
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error("FFmpeg segment error: %s", result.stderr[-500:] if result.stderr else "")
            raise RuntimeError(f"FFmpeg segment render failed: {result.stderr[-200:]}")

    def _build_segment_from_video(
        self,
        video_path: str,
        duration: float,
        output_path: str,
        width: int,
        height: int,
    ) -> None:
        """Scale, loop, and trim a video clip to fill the target duration."""
        # Use -stream_loop to loop short clips to fill the target duration
        # Re-encode at the target fps to avoid judder from fps mismatch
        cmd = [
            self.ffmpeg_path, "-y",
            "-stream_loop", "-1",
            "-i", video_path,
            "-vf", (
                f"scale={width}:{height}:force_original_aspect_ratio=increase,"
                f"crop={width}:{height},"
                f"fps={self.fps},"
                f"format=yuv420p"
            ),
            "-t", str(duration),
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23",
            "-an",
            "-pix_fmt", "yuv420p",
            output_path,
        ]

        logger.debug("Running: %s", " ".join(cmd))
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error("FFmpeg video segment error: %s", result.stderr[-500:] if result.stderr else "")
            raise RuntimeError(f"FFmpeg video segment render failed: {result.stderr[-200:]}")

    def _build_caption_filter(
        self, captions: CaptionData, width: int, height: int
    ) -> str:
        """Build FFmpeg drawtext filter for word-by-word captions."""
        if not captions.words:
            return ""

        # Position captions in the lower third
        x = f"(w-text_w)/2"
        y = f"h*0.80"
        fontsize = int(width * 0.065)

        filters = []
        for word in captions.words:
            escaped = _escape_drawtext(word.word)
            enable = f"between(t,{word.start:.3f},{word.end:.3f})"
            filters.append(
                f"drawtext=text='{escaped}':fontsize={fontsize}"
                f":fontcolor=white:borderw=3:bordercolor=black"
                f":x={x}:y={y}:enable='{enable}'"
            )

        return ",".join(filters)

    def render(
        self,
        script: Script,
        audio: AudioAsset,
        visuals: list[VisualAsset],
        captions: CaptionData,
        config: dict,
    ) -> str:
        """Composite final video from images, audio, and captions."""
        resolution = config.get("resolution", self.resolution)
        width, height = (int(x) for x in resolution.split("x"))

        tmpdir = tempfile.mkdtemp(prefix="reelforge_render_")
        segment_files = []

        # Sort visuals by segment_id
        sorted_visuals = sorted(visuals, key=lambda v: v.segment_id)

        # Get actual audio duration and compute proportional segment durations
        ffprobe_path = shutil.which("ffprobe") or "ffprobe"
        audio_duration = _get_audio_duration(ffprobe_path, audio.path)
        script_durations = [
            script.segments[i].duration_seconds if i < len(script.segments) else 5.0
            for i in range(len(sorted_visuals))
        ]
        script_total = sum(script_durations) or 1.0

        if audio_duration > 0:
            # Scale segment durations proportionally to match actual audio length
            segment_durations = [
                d / script_total * audio_duration for d in script_durations
            ]
            logger.info(
                "Audio duration: %.1fs, script total: %.1fs — scaling segment durations",
                audio_duration, script_total,
            )
        else:
            segment_durations = script_durations
            logger.warning("Could not detect audio duration, using script estimates")

        # Step 1: Create video clips for each segment
        for i, visual in enumerate(sorted_visuals):
            duration = segment_durations[i]

            segment_path = f"{tmpdir}/segment_{i:03d}.mp4"
            logger.info(
                "Building segment %d: %s (%.1fs, type=%s)",
                i, visual.path, duration, visual.type,
            )

            if visual.type == "video":
                self._build_segment_from_video(visual.path, duration, segment_path, width, height)
            else:
                self._build_segment_video(visual.path, duration, segment_path, width, height)
            segment_files.append(segment_path)

        if not segment_files:
            raise RuntimeError("No segment videos were created")

        # Step 2: Create concat file
        concat_path = f"{tmpdir}/concat.txt"
        with open(concat_path, "w") as f:
            for sf in segment_files:
                f.write(f"file '{sf}'\n")

        # Step 3: Concatenate segments
        concat_output = f"{tmpdir}/concat.mp4"
        cmd = [
            self.ffmpeg_path, "-y",
            "-f", "concat", "-safe", "0",
            "-i", concat_path,
            "-c", "copy",
            concat_output,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg concat failed: {result.stderr[-200:]}")

        # Step 4: Add audio + captions
        output_path = f"{tmpdir}/output.mp4"
        caption_filter = self._build_caption_filter(captions, width, height)

        vf_filters = []
        if caption_filter:
            vf_filters.append(caption_filter)

        cmd = [
            self.ffmpeg_path, "-y",
            "-i", concat_output,
            "-i", audio.path,
            "-map", "0:v",
            "-map", "1:a",
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "128k",
            "-shortest",
        ]

        if vf_filters:
            cmd.extend(["-vf", ",".join(vf_filters)])

        cmd.extend(["-pix_fmt", "yuv420p", output_path])

        logger.info("Compositing final video with audio and captions")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg final render failed: {result.stderr[-200:]}")

        logger.info("Video rendered: %s", output_path)
        return output_path
