"""AnimateDiff visual provider — local text-to-video via Stable Diffusion + motion adapter."""

from __future__ import annotations

import logging
from pathlib import Path

from reelforge.providers.base import SegmentBrief, VisualAsset, VisualProvider

logger = logging.getLogger(__name__)


class AnimateDiffVisual(VisualProvider):
    """Visual provider using AnimateDiff for short video clip generation."""

    def __init__(
        self,
        model_id: str = "stable-diffusion-v1-5/stable-diffusion-v1-5",
        motion_adapter_id: str = "guoyww/animatediff-motion-adapter-v1-5-3",
        num_inference_steps: int = 15,
        num_frames: int = 8,
        width: int = 256,
        height: int = 256,
        fps: int = 8,
        output_dir: str = ".",
        **kwargs,
    ) -> None:
        self.model_id = model_id
        self.motion_adapter_id = motion_adapter_id
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

            # Help ROCm handle fragmented VRAM on small GPUs
            os.environ.setdefault("PYTORCH_HIP_ALLOC_CONF", "expandable_segments:True")

            # Ensure GPU is clean before loading
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
                logger.info(
                    "GPU before AnimateDiff load — allocated: %.1f MiB",
                    torch.cuda.memory_allocated() / 1024 / 1024,
                )

            from diffusers import AnimateDiffPipeline, DDIMScheduler, MotionAdapter

            logger.info("Loading motion adapter: %s", self.motion_adapter_id)
            adapter = MotionAdapter.from_pretrained(
                self.motion_adapter_id,
                torch_dtype=torch.float16,
            )

            logger.info("Loading AnimateDiff pipeline: %s", self.model_id)
            self._pipe = AnimateDiffPipeline.from_pretrained(
                self.model_id,
                motion_adapter=adapter,
                torch_dtype=torch.float16,
            )
            self._pipe.scheduler = DDIMScheduler.from_pretrained(
                self.model_id,
                subfolder="scheduler",
                clip_sample=False,
                timestep_spacing="linspace",
                beta_schedule="linear",
                steps_offset=1,
            )
            self._pipe.vae.enable_slicing()
            self._pipe.vae.enable_tiling()

            # Use sequential CPU offload — moves layers to GPU one at a time
            # Required on GPUs with <4GB free VRAM (e.g. shared display + compute)
            self._pipe.enable_sequential_cpu_offload()
            # Slice attention to reduce peak VRAM during inference
            self._pipe.enable_attention_slicing("auto")
            logger.info("AnimateDiff loaded with sequential CPU offload + attention slicing")

        return self._pipe

    def get_visuals(
        self, segments: list[SegmentBrief], style: dict
    ) -> list[VisualAsset]:
        """Generate one video clip per segment using AnimateDiff."""
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
                    negative_prompt="bad quality, blurry, low resolution",
                    num_frames=self.num_frames,
                    num_inference_steps=self.num_inference_steps,
                    height=self.height,
                    width=self.width,
                    guidance_scale=7.5,
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
        """Release GPU memory held by the AnimateDiff pipeline."""
        if self._pipe is not None:
            del self._pipe
            self._pipe = None
            try:
                import torch, gc
                gc.collect()
                torch.cuda.empty_cache()
            except Exception:
                pass
            logger.info("AnimateDiff pipeline released")
