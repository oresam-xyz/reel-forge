"""Post-render video compression using PyAV (libav/FFmpeg bindings).

Re-encodes the rendered video with H.265 (HEVC) for ~50% smaller files
at the same visual quality as the H.264 source.
"""

from __future__ import annotations

import logging
import warnings
from pathlib import Path

logger = logging.getLogger(__name__)


def compress_video(
    input_path: str,
    output_path: str | None = None,
    codec: str = "libx265",
    crf: int = 28,
    preset: str = "medium",
    audio_bitrate: int = 96_000,
) -> str:
    """Compress a video file using PyAV.

    Args:
        input_path: Path to the source video.
        output_path: Path for compressed output. Defaults to replacing the input.
        codec: Video codec (libx265 for HEVC, libx264 for AVC).
        crf: Constant Rate Factor — lower = better quality, bigger file.
             28 is default for x265 (visually ~equivalent to x264 CRF 23).
        preset: Encoding speed/compression tradeoff (ultrafast..veryslow).
        audio_bitrate: Audio bitrate in bps. 96k is fine for speech.

    Returns:
        Path to the compressed file.
    """
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="builtin type swigvarlink")
        import av

    if output_path is None:
        # Write to temp, then replace
        output_path = str(Path(input_path).with_suffix(".compressed.mp4"))
        replace_original = True
    else:
        replace_original = False

    input_size = Path(input_path).stat().st_size

    logger.info(
        "Compressing video: %s (%.1f MB) → codec=%s crf=%d preset=%s",
        input_path,
        input_size / 1024 / 1024,
        codec,
        crf,
        preset,
    )

    input_container = av.open(input_path, mode="r")
    output_container = av.open(output_path, mode="w")

    # Set up video stream
    in_video = input_container.streams.video[0]
    out_video = output_container.add_stream(codec, rate=in_video.average_rate)
    out_video.width = in_video.width
    out_video.height = in_video.height
    out_video.pix_fmt = "yuv420p"
    out_video.options = {
        "crf": str(crf),
        "preset": preset,
        "x265-params": "log-level=warning",
    }
    # Tag as hvc1 for broad player compatibility (Apple, web, etc.)
    if "265" in codec or "hevc" in codec.lower():
        out_video.codec_context.codec_tag = "hvc1"

    # Set up audio stream
    in_audio = input_container.streams.audio[0]
    out_audio = output_container.add_stream("aac", rate=in_audio.rate)
    out_audio.bit_rate = audio_bitrate
    out_audio.layout = in_audio.layout

    # Re-encode all packets
    for packet in input_container.demux():
        if packet.stream.type == "video":
            for frame in packet.decode():
                for out_packet in out_video.encode(frame):
                    output_container.mux(out_packet)
        elif packet.stream.type == "audio":
            for frame in packet.decode():
                frame.pts = None  # let encoder set pts
                for out_packet in out_audio.encode(frame):
                    output_container.mux(out_packet)

    # Flush encoders
    for out_packet in out_video.encode():
        output_container.mux(out_packet)
    for out_packet in out_audio.encode():
        output_container.mux(out_packet)

    output_container.close()
    input_container.close()

    output_size = Path(output_path).stat().st_size
    reduction = (1 - output_size / input_size) * 100 if input_size > 0 else 0

    logger.info(
        "Compression complete: %.1f MB → %.1f MB (%.0f%% reduction)",
        input_size / 1024 / 1024,
        output_size / 1024 / 1024,
        reduction,
    )

    if replace_original:
        import shutil
        shutil.move(output_path, input_path)
        logger.info("Replaced original with compressed file")
        return input_path

    return output_path
