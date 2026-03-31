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
        num_frames: int = 33,
        width: int = 480,
        height: int = 832,
        fps: int = 16,
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
            try:
                import torch
                from diffusers import AutoencoderKLWan, WanPipeline
                from diffusers.utils import export_to_video
            except ImportError:
                raise ImportError(
                    "The 'diffusers' and 'torch' packages are required for Wan. "
                    "Install with: pip install diffusers torch"
                )
            import torch

            logger.info("Loading Wan2.1 model: %s", self.model_id)

            try:
                vae = AutoencoderKLWan.from_pretrained(
                    self.model_id,
                    subfolder="vae",
                    torch_dtype=torch.float32,
                )

                self._pipe = WanPipeline.from_pretrained(
                    self.model_id,
                    vae=vae,
                    torch_dtype=torch.bfloat16,
                )
                self._pipe.enable_model_cpu_offload()
            except Exception as e:
                logger.warning("Failed to initialize model on CUDA: %s. "
                               "Try setting device='cpu' or check CUDA installation.", e)
                # Fallback: load to CPU first, then move
                vae = AutoencoderKLWan.from_pretrained(
                    self.model_id,
                    subfolder="vae",
                    torch_dtype=torch.float32,
                    low_cpu_mem_usage=False,
                )

                self._pipe = WanPipeline.from_pretrained(
                    self.model_id,
                    vae=vae,
                    torch_dtype=torch.bfloat16,
                    low_cpu_mem_usage=False,
                )
                self._pipe.to("cuda")

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
