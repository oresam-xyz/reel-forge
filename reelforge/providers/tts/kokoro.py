"""Kokoro TTS provider — local text-to-speech via the kokoro library."""

from __future__ import annotations

import logging
from pathlib import Path

from reelforge.providers.base import AudioAsset, TTSProvider

logger = logging.getLogger(__name__)


class KokoroTTS(TTSProvider):
    """TTS provider using the local Kokoro model."""

    def __init__(self, voice_id: str = "af_heart", speed: float = 1.0, **kwargs) -> None:
        self.default_voice_id = voice_id
        self.default_speed = speed
        self._pipeline = None

    def _get_pipeline(self):
        if self._pipeline is None:
            try:
                from kokoro import KPipeline
            except ImportError:
                raise ImportError(
                    "The 'kokoro' package is required for Kokoro TTS. "
                    "Install it with: pip install kokoro"
                )
            # Auto-detect language from voice ID first character (a=American, b=British, etc.)
            lang_code = self.default_voice_id[0] if self.default_voice_id else "a"
            self._pipeline = KPipeline(lang_code=lang_code)
            logger.info("Kokoro pipeline initialised (lang=%s)", lang_code)
        return self._pipeline

    def synthesise(self, text: str, voice_profile: dict) -> AudioAsset:
        """Synthesise speech from text using Kokoro."""
        import soundfile as sf

        pipeline = self._get_pipeline()

        voice_id = voice_profile.get("voice_id", self.default_voice_id)
        speed = voice_profile.get("speed", self.default_speed)
        output_path = voice_profile.get("output_path", "audio.wav")

        logger.info(
            "Synthesising %d characters with voice=%s, speed=%.1f",
            len(text), voice_id, speed,
        )

        # Generate audio — kokoro returns generator of (graphemes, phonemes, audio) tuples
        all_audio = []
        for _, _, audio in pipeline(text, voice=voice_id, speed=speed):
            all_audio.append(audio)

        if not all_audio:
            raise RuntimeError("Kokoro produced no audio output")

        # Concatenate all audio chunks
        import numpy as np
        combined = np.concatenate(all_audio)

        # Write to WAV (Kokoro outputs at 24kHz)
        sf.write(output_path, combined, 24000)

        duration = len(combined) / 24000.0
        logger.info("Audio saved: %s (%.1fs)", output_path, duration)

        return AudioAsset(path=str(output_path), duration_seconds=duration)
