"""Pipeline runner — reads state, resumes from last completed phase."""

from __future__ import annotations

import logging
from typing import Callable

from reelforge.agent.brand import BrandIdentity
from reelforge.agent.project import PHASES, Project
from reelforge.config import AppConfig
from reelforge.providers.base import (
    LLMProvider,
    Providers,
    RendererProvider,
    TTSProvider,
    VisualProvider,
    PhaseStatus,
)

logger = logging.getLogger(__name__)

# Phase function type: run(project, brand, providers) -> None
PhaseFunc = Callable[[Project, BrandIdentity, Providers], None]


def _get_phase_func(phase_name: str) -> PhaseFunc:
    """Lazy-import and return the run() function for a given phase."""
    if phase_name == "research":
        from reelforge.agent.phases.research import run
        return run
    elif phase_name == "planning":
        from reelforge.agent.phases.planning import run
        return run
    elif phase_name == "review":
        from reelforge.agent.phases.review import run
        return run
    elif phase_name == "script":
        from reelforge.agent.phases.script import run
        return run
    elif phase_name == "assets":
        from reelforge.agent.phases.assets import run
        return run
    elif phase_name == "render":
        from reelforge.agent.phases.render import run
        return run
    else:
        raise ValueError(f"Unknown phase: {phase_name}")


def _get_provider_class(category: str, provider_name: str) -> type:
    """Lazy-import and return a provider class by category and name."""
    if category == "llm":
        if provider_name == "ollama":
            from reelforge.providers.llm.ollama import OllamaLLM
            return OllamaLLM
        elif provider_name == "claude":
            from reelforge.providers.llm.claude import ClaudeLLM
            return ClaudeLLM
        elif provider_name == "openrouter":
            from reelforge.providers.llm.openrouter import OpenRouterLLM
            return OpenRouterLLM
    elif category == "tts":
        if provider_name == "kokoro":
            from reelforge.providers.tts.kokoro import KokoroTTS
            return KokoroTTS
        elif provider_name == "coqui":
            from reelforge.providers.tts.coqui import CoquiTTS
            return CoquiTTS
        elif provider_name == "elevenlabs":
            from reelforge.providers.tts.elevenlabs import ElevenLabsTTS
            return ElevenLabsTTS
    elif category == "visuals":
        if provider_name == "flux":
            from reelforge.providers.visuals.flux import FluxVisual
            return FluxVisual
        elif provider_name == "wan":
            from reelforge.providers.visuals.wan import WanVisual
            return WanVisual
        elif provider_name == "animatediff":
            from reelforge.providers.visuals.animatediff import AnimateDiffVisual
            return AnimateDiffVisual
        elif provider_name == "pexels":
            from reelforge.providers.visuals.pexels import PexelsVisual
            return PexelsVisual
        elif provider_name in ("falai", "fal", "cogvideox-5b", "kling-1.6", "wan-t2v"):
            from reelforge.providers.visuals.falai import FalAIVisual
            return FalAIVisual
    elif category == "renderer":
        if provider_name == "ffmpeg":
            from reelforge.providers.renderer.ffmpeg import FFmpegRenderer
            return FFmpegRenderer
    raise ValueError(f"Unknown provider: {category}/{provider_name}")


def instantiate_providers(config: AppConfig) -> Providers:
    """Create provider instances from config."""
    providers = {}
    for category in ("llm", "tts", "visuals", "renderer"):
        pconf = config.providers.get(category)
        if pconf is None:
            raise ValueError(f"No provider configured for '{category}'")
        provider_name = pconf.provider
        cls = _get_provider_class(category, provider_name)
        # Pass all extra config fields as kwargs to the provider constructor
        extra = {k: v for k, v in pconf.model_dump().items() if k != "provider"}
        providers[category] = cls(**extra)
        logger.info("Instantiated %s provider: %s", category, provider_name)

    return Providers(
        llm=providers["llm"],
        tts=providers["tts"],
        visual=providers["visuals"],
        renderer=providers["renderer"],
    )


def run_pipeline(
    project: Project,
    brand: BrandIdentity,
    providers: Providers,
    phase_overrides: dict[str, PhaseFunc] | None = None,
) -> None:
    """Execute the pipeline, skipping completed phases and resuming from the first pending/failed one."""
    logger.info(
        "Starting pipeline for project '%s' (topic: %s)",
        project.state.project_id,
        project.state.topic,
    )

    for phase_name in PHASES:
        phase_info = project.state.phases[phase_name]

        if phase_info.status == PhaseStatus.COMPLETE:
            logger.info("Skipping completed phase: %s", phase_name)
            continue

        logger.info("Running phase: %s", phase_name)
        project.mark_phase_running(phase_name)

        try:
            if phase_overrides and phase_name in phase_overrides:
                phase_func = phase_overrides[phase_name]
            else:
                phase_func = _get_phase_func(phase_name)
            phase_func(project, brand, providers)
            project.mark_phase_complete(phase_name)
        except Exception as e:
            project.mark_phase_failed(phase_name, str(e))
            logger.exception("Pipeline halted at phase '%s'", phase_name)
            raise

    logger.info("Pipeline completed for project '%s'", project.state.project_id)
