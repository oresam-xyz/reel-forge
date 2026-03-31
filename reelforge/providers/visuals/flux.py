"""FLUX.1 visual provider — local image generation via diffusers."""

from __future__ import annotations

import logging
from pathlib import Path

from reelforge.providers.base import SegmentBrief, VisualAsset, VisualProvider

logger = logging.getLogger(__name__)


class FluxVisual(VisualProvider):
    """Visual provider using local FLUX.1 model via the diffusers library."""

    def __init__(
        self,
        model_id: str = "black-forest-labs/FLUX.1-schnell",
        num_inference_steps: int = 4,
        width: int = 512,
        height: int = 912,
        output_dir: str = ".",
        **kwargs,
    ) -> None:
        self.model_id = model_id
        self.num_inference_steps = num_inference_steps
        self.width = width
        self.height = height
        self.output_dir = output_dir
        self._pipe = None

    def _get_pipeline(self):
        if self._pipe is None:
            try:
                import torch
                from diffusers import FluxPipeline
            except ImportError:
                raise ImportError(
                    "The 'diffusers' and 'torch' packages are required for Flux. "
                    "Install with: pip install diffusers torch"
                )
            logger.info("Loading FLUX model: %s", self.model_id)
            self._pipe = FluxPipeline.from_pretrained(
                self.model_id,
                torch_dtype=torch.bfloat16,
            )
            self._pipe.enable_model_cpu_offload()
        return self._pipe

    def get_visuals(
        self, segments: list[SegmentBrief], style: dict
    ) -> list[VisualAsset]:
        """Generate one image per segment using FLUX.1."""
        import torch

        pipe = self._get_pipeline()
        # Use output_dir from style if provided (set by assets phase), else fallback
        output_dir = Path(style.get("output_dir", self.output_dir))
        output_dir.mkdir(parents=True, exist_ok=True)

        assets = []
        for seg in segments:
            prompt = seg.visual_brief
            output_path = output_dir / f"img_{seg.segment_id:02d}.png"

            logger.info("Generating image for segment %d: %s", seg.segment_id, prompt[:80])

            with torch.inference_mode():
                image = pipe(
                    prompt,
                    num_inference_steps=self.num_inference_steps,
                    width=self.width,
                    height=self.height,
                    guidance_scale=0.0,
                ).images[0]

            image.save(output_path)
            logger.info("Image saved: %s", output_path)

            assets.append(VisualAsset(
                path=str(output_path),
                segment_id=seg.segment_id,
                type="image",
            ))

            # Free VRAM between generations
            torch.cuda.empty_cache()

        return assets
