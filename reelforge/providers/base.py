"""Data models and abstract base classes for all ReelForge providers."""

from __future__ import annotations

import enum
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Provider error types
# ---------------------------------------------------------------------------

class ProviderCreditError(Exception):
    """Raised when a provider rejects a request due to insufficient credits / quota."""

    def __init__(self, provider: str, detail: str = "") -> None:
        self.provider = provider
        self.detail = detail
        super().__init__(f"[CREDIT_LIMIT:{provider}] {detail}" if detail else f"[CREDIT_LIMIT:{provider}]")


def raise_if_credit_error(response: Any, provider: str) -> None:
    """Check an httpx Response for credit/quota errors and raise ProviderCreditError if found.

    Covers HTTP 402 (payment required) and common 401/403/429 bodies that
    mention credits, quota, or billing across fal.ai, ElevenLabs, and OpenRouter.
    Call this *before* response.raise_for_status() on any billing-sensitive request.
    """
    status = response.status_code
    if status == 402:
        try:
            body = response.json()
            detail = (
                body.get("detail")
                or body.get("message")
                or body.get("error", {}).get("message", "")
                or str(body)
            )
        except Exception:
            detail = response.text[:200]
        raise ProviderCreditError(provider, detail or "Insufficient credits")

    # Some services return 401/403/429 for quota exhaustion — check body keywords
    if status in (401, 403, 429):
        try:
            text = response.text.lower()
        except Exception:
            return
        if any(kw in text for kw in ("quota", "credit", "billing", "limit exceeded", "out of credits", "insufficient")):
            try:
                body = response.json()
                detail = body.get("detail") or body.get("message") or body.get("error", {}).get("message", "") or text[:200]
            except Exception:
                detail = text[:200]
            raise ProviderCreditError(provider, str(detail))


# ---------------------------------------------------------------------------
# Brand Identity Models
# ---------------------------------------------------------------------------

class Persona(BaseModel):
    character: str
    speaks_as: str
    always_does: list[str] = Field(default_factory=list)
    never_does: list[str] = Field(default_factory=list)


class Tone(BaseModel):
    voice: str
    reading_pace: str = "medium"
    vocabulary: str = "conversational"


class VisualStyle(BaseModel):
    aesthetic: str = ""
    colour_palette: list[str] = Field(default_factory=list)
    caption_style: str = "word_by_word"
    image_prompt_prefix: str = ""


class VoiceProfile(BaseModel):
    provider: str = "kokoro"
    voice_id: str = ""
    speed: float = 1.0
    pitch_adjust: float = 0.0


class BrandIdentityData(BaseModel):
    name: str
    persona: Persona
    tone: Tone
    visual_style: VisualStyle = Field(default_factory=VisualStyle)
    voice_profile: VoiceProfile = Field(default_factory=VoiceProfile)
    # text → spoken pronunciation map; captions show the original text
    pronunciations: dict[str, str] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Research Models
# ---------------------------------------------------------------------------

class ResearchSource(BaseModel):
    url: str
    title: str
    summary: str


class ResearchNotes(BaseModel):
    queries: list[str] = Field(default_factory=list)
    sources: list[ResearchSource] = Field(default_factory=list)
    key_facts: list[str] = Field(default_factory=list)
    completed_at: str = ""


# ---------------------------------------------------------------------------
# Content Plan Models
# ---------------------------------------------------------------------------

class Segment(BaseModel):
    narration: str
    visual_brief: str
    duration_seconds: int = 5


class ContentPlan(BaseModel):
    hook: str
    segments: list[Segment] = Field(default_factory=list)
    cta: str = ""
    tone_guidance: str = ""
    estimated_duration_seconds: int = 60
    approved: bool = False
    edit_rounds: int = 0


# ---------------------------------------------------------------------------
# Script Models
# ---------------------------------------------------------------------------

class ScriptSegment(BaseModel):
    segment_id: int
    narration: str
    visual_prompt: str
    duration_seconds: float = 5.0


class Script(BaseModel):
    title: str
    segments: list[ScriptSegment] = Field(default_factory=list)
    total_duration: float = 0.0


# ---------------------------------------------------------------------------
# Asset Models
# ---------------------------------------------------------------------------

class AudioAsset(BaseModel):
    path: str
    duration_seconds: float = 0.0


class VisualAsset(BaseModel):
    path: str
    segment_id: int
    type: str = "image"  # image | video


class WordTimestamp(BaseModel):
    word: str
    start: float
    end: float


class CaptionData(BaseModel):
    words: list[WordTimestamp] = Field(default_factory=list)


class SegmentBrief(BaseModel):
    segment_id: int
    visual_brief: str
    duration_seconds: float = 5.0


# ---------------------------------------------------------------------------
# Project State Models
# ---------------------------------------------------------------------------

class PhaseStatus(str, enum.Enum):
    PENDING = "pending"
    COMPLETE = "complete"
    FAILED = "failed"


class PhaseInfo(BaseModel):
    status: PhaseStatus = PhaseStatus.PENDING
    completed_at: str | None = None
    error: str | None = None


class ProjectState(BaseModel):
    project_id: str
    brand: str
    topic: str
    created_at: str
    phases: dict[str, PhaseInfo] = Field(default_factory=dict)
    current_phase: str = "research"
    regeneration_notes: str = ""


# ---------------------------------------------------------------------------
# Abstract Provider Base Classes
# ---------------------------------------------------------------------------

class LLMProvider(ABC):
    @abstractmethod
    def generate(self, prompt: str, system: str = "") -> str:
        """Generate a free-form text response."""
        ...

    @abstractmethod
    def generate_json(self, prompt: str, system: str = "") -> dict:
        """Generate a response and parse it as JSON."""
        ...


class TTSProvider(ABC):
    @abstractmethod
    def synthesise(self, text: str, voice_profile: dict) -> AudioAsset:
        """Synthesise speech from text. Returns an AudioAsset with the output path."""
        ...


class VisualProvider(ABC):
    @abstractmethod
    def get_visuals(
        self, segments: list[SegmentBrief], style: dict
    ) -> list[VisualAsset]:
        """Generate or fetch visuals for each segment brief."""
        ...


class RendererProvider(ABC):
    @abstractmethod
    def render(
        self,
        script: Script,
        audio: AudioAsset,
        visuals: list[VisualAsset],
        captions: CaptionData,
        config: dict,
    ) -> str:
        """Composite final video. Returns the output file path."""
        ...


# ---------------------------------------------------------------------------
# Provider Bundle
# ---------------------------------------------------------------------------

@dataclass
class Providers:
    llm: LLMProvider
    tts: TTSProvider
    visual: VisualProvider
    renderer: RendererProvider
