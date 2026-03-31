"""Wan2.1 visual provider — local text-to-video generation via diffusers."""

from __future__ import annotations

import logging
from pathlib import Path

from reelforge.providers.base import SegmentBrief, VisualAsset, VisualProvider

logger = logging.getLogger(__name__)


class WanVisual(VisualProvider):
    """Visual provider using Wan2.1-T2V-1.3B for video clip generation."""

    def __init__(
        self,
        model_id: str = "Wan-AI/Wan2.1-T2V-1.3B-Diffusers",
        num_inference_steps: int = 25,
        num_frames: int = 17,
        width: int = 480,
        height: int = 480,
        fps: int = 8,
        output_dir: str = ".",
        **kwargs,
    ) -> None:
        self.model_id = model_id
        self.num_inference_steps = num_inference_steps
        self.num_frames = num_frames
        self.width = width
        self.height = height
        self.fps = fps
        self.output_dir = output_dir
        self._pipe = None

    def _get_pipeline(self):
        if self._pipe is None:
            import gc
            import os
            import torch

            os.environ.setdefault("PYTORCH_HIP_ALLOC_CONF", "expandable_segments:True")

            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
                logger.info(
                    "GPU before Wan load — allocated: %.1f MiB",
                    torch.cuda.memory_allocated() / 1024 / 1024,
                )

            from diffusers import AutoencoderKLWan, WanPipeline

            logger.info("Loading Wan2.1 model: %s", self.model_id)

            vae = AutoencoderKLWan.from_pretrained(
                self.model_id,
                subfolder="vae",
                torch_dtype=torch.float32,
            )

            # Use float16 instead of bfloat16 — better ROCm gfx1030 support
            self._pipe = WanPipeline.from_pretrained(
                self.model_id,
                vae=vae,
                torch_dtype=torch.float16,
            )

            # Sequential CPU offload moves one layer at a time to GPU
            # Required for GPUs with limited free VRAM (shared display)
            self._pipe.enable_sequential_cpu_offload()
            self._pipe.enable_attention_slicing("auto")
            self._pipe.vae.enable_slicing()
            self._pipe.vae.enable_tiling()
            logger.info("Wan2.1 loaded with sequential CPU offload + attention slicing")

        return self._pipe

    def get_visuals(
        self, segments: list[SegmentBrief], style: dict
    ) -> list[VisualAsset]:
        """Generate one video clip per segment using Wan2.1."""
        import torch
        from diffusers.utils import export_to_video

        pipe = self._get_pipeline()
        output_dir = Path(style.get("output_dir", self.output_dir))
        output_dir.mkdir(parents=True, exist_ok=True)

        assets = []
        for seg in segments:
            prompt = seg.visual_brief
            output_path = output_dir / f"clip_{seg.segment_id:02d}.mp4"

            logger.info(
                "Generating video for segment %d: %s",
                seg.segment_id, prompt[:80],
            )

            with torch.inference_mode():
                output = pipe(
                    prompt=prompt,
                    num_frames=self.num_frames,
                    num_inference_steps=self.num_inference_steps,
                    height=self.height,
                    width=self.width,
                    guidance_scale=5.0,
                )

            export_to_video(output.frames[0], str(output_path), fps=self.fps)
            logger.info("Video clip saved: %s", output_path)

            assets.append(VisualAsset(
                path=str(output_path),
                segment_id=seg.segment_id,
                type="video",
            ))

            torch.cuda.empty_cache()

        return assets

    def release(self) -> None:
        """Release GPU memory held by the Wan pipeline."""
        if self._pipe is not None:
            del self._pipe
            self._pipe = None
        try:
            import gc
            gc.collect()
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
            gc.collect()
            logger.info("Wan pipeline released")
        except Exception as e:
            logger.warning("Wan release cleanup error: %s", e)
