"""fal.ai visual provider — AI video generation via fal.ai cloud API."""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path

import httpx

from reelforge.providers.base import SegmentBrief, VisualAsset, VisualProvider

logger = logging.getLogger(__name__)

# fal.ai model IDs
_MODELS = {
    # CogVideoX
    "cogvideox-5b": "fal-ai/cogvideox-5b",
    # Kling (newest first)
    "kling-3-pro": "fal-ai/kling-video/v3/pro/text-to-video",
    "kling-2.6-pro": "fal-ai/kling-video/v2.6/pro/text-to-video",
    "kling-2.1-master": "fal-ai/kling-video/v2.1/master/text-to-video",
    "kling-2.0-master": "fal-ai/kling-video/v2/master/text-to-video",
    "kling-1.6": "fal-ai/kling-video/v1.6/standard/text-to-video",
    # Wan
    "wan-2.2": "fal-ai/wan-2.2/text-to-video",
    "wan-t2v": "fal-ai/wan-t2v",
    # Google Veo
    "veo-3.1": "fal-ai/veo3.1",
    # LTX
    "ltx-video": "fal-ai/ltx-video",
    # Seedance
    "seedance-2": "fal-ai/seedance-2/text-to-video",
}

_FAL_QUEUE_URL = "https://queue.fal.run"
_FAL_RUN_URL = "https://fal.run"

_PRICES_PER_SECOND = {
    "fal-ai/cogvideox-5b": 0.020,
    "fal-ai/kling-video/v1.6/standard/text-to-video": 0.030,
    "fal-ai/kling-video/v2/master/text-to-video": 0.040,
    "fal-ai/kling-video/v2.1/master/text-to-video": 0.050,
    "fal-ai/kling-video/v2.6/pro/text-to-video": 0.070,
    "fal-ai/kling-video/v3/pro/text-to-video": 0.224,
    "fal-ai/wan-t2v": 0.030,
    "fal-ai/wan-2.2/text-to-video": 0.100,
    "fal-ai/veo3.1": 0.200,
    "fal-ai/ltx-video": 0.040,
    "fal-ai/seedance-2/text-to-video": 0.300,
}


class FalAIVisual(VisualProvider):
    """Visual provider using fal.ai for AI video generation."""

    def __init__(
        self,
        api_key: str = "",
        model: str = "cogvideox-5b",
        num_frames: int = 49,
        fps: int = 8,
        num_inference_steps: int = 50,
        **kwargs,
    ) -> None:
        self._api_key = api_key or os.environ.get("FAL_KEY", "")
        if not self._api_key:
            raise ValueError("fal.ai API key required. Set fal_api_key in config or FAL_KEY env var.")
        self._model_id = _MODELS.get(model, model)
        self._num_frames = num_frames
        self._fps = fps
        self._num_inference_steps = num_inference_steps
        self._client = httpx.Client(
            timeout=300.0,
            headers={
                "Authorization": f"Key {self._api_key}",
                "Content-Type": "application/json",
            },
        )
        self.cost_usd: float = 0.0

    def _generate_clip(self, prompt: str, duration_seconds: float) -> bytes:
        """Submit a text-to-video job and return the raw video bytes."""
        # CogVideoX generates fixed 6s at 8fps (49 frames); other models vary
        payload = {
            "prompt": prompt,
            "num_frames": self._num_frames,
            "fps": self._fps,
            "num_inference_steps": self._num_inference_steps,
        }

        # Submit to queue using full model path
        submit_url = f"{_FAL_QUEUE_URL}/{self._model_id}"
        resp = self._client.post(submit_url, json=payload)
        resp.raise_for_status()
        request_id = resp.json()["request_id"]
        # Status/result use only owner/alias (first two path segments), not the versioned tail
        parts = self._model_id.split("/")
        owner_alias = f"{parts[0]}/{parts[1]}"
        status_url = f"{_FAL_QUEUE_URL}/{owner_alias}/requests/{request_id}/status"
        result_url = f"{_FAL_QUEUE_URL}/{owner_alias}/requests/{request_id}"

        logger.info("fal.ai job submitted: %s (request_id=%s)", self._model_id, request_id)

        # Poll until complete
        for _ in range(120):
            time.sleep(5)
            status_resp = self._client.get(status_url)
            status_resp.raise_for_status()
            status = status_resp.json().get("status")
            logger.debug("fal.ai status: %s", status)
            if status == "COMPLETED":
                break
            if status in ("FAILED", "CANCELLED"):
                raise RuntimeError(f"fal.ai job {status.lower()}: {status_resp.json()}")
        else:
            raise TimeoutError("fal.ai job timed out after 10 minutes")

        # Fetch result
        result_resp = self._client.get(result_url)
        result_resp.raise_for_status()
        result = result_resp.json()

        video_url = (
            result.get("video", {}).get("url")
            or (result.get("videos") or [{}])[0].get("url")
        )
        if not video_url:
            raise RuntimeError(f"No video URL in fal.ai result: {result}")

        logger.info("Downloading generated clip from: %s", video_url[:80])
        video_resp = self._client.get(video_url)
        video_resp.raise_for_status()
        return video_resp.content

    def get_visuals(self, segments: list[SegmentBrief], style: dict) -> list[VisualAsset]:
        """Generate one AI video clip per segment."""
        output_dir = Path(style.get("output_dir", "."))
        output_dir.mkdir(parents=True, exist_ok=True)

        prefix = style.get("image_prompt_prefix", "")
        assets = []

        for seg in segments:
            prompt = seg.visual_brief
            if prefix and not prompt.startswith(prefix):
                prompt = f"{prefix} {prompt}"

            output_path = output_dir / f"clip_{seg.segment_id:02d}.mp4"

            if output_path.exists() and output_path.stat().st_size > 0:
                logger.info("Clip already exists, skipping: %s", output_path)
                assets.append(VisualAsset(path=str(output_path), segment_id=seg.segment_id, type="video"))
                price = _PRICES_PER_SECOND.get(self._model_id, 0.05)
                self.cost_usd += seg.duration_seconds * price
                continue

            logger.info(
                "Generating clip for segment %d (%ds): %s",
                seg.segment_id, seg.duration_seconds, prompt[:80],
            )

            try:
                video_bytes = self._generate_clip(prompt, seg.duration_seconds)
                output_path.write_bytes(video_bytes)
                logger.info("Clip saved: %s (%d bytes)", output_path, len(video_bytes))
                assets.append(VisualAsset(path=str(output_path), segment_id=seg.segment_id, type="video"))
                price = _PRICES_PER_SECOND.get(self._model_id, 0.05)
                self.cost_usd += seg.duration_seconds * price
            except Exception as e:
                logger.error("Failed to generate clip for segment %d: %s", seg.segment_id, e)
                raise

        return assets

    def release(self) -> None:
        pass

    def close(self) -> None:
        self._client.close()
