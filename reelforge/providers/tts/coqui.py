"""Coqui TTS provider — local text-to-speech via the TTS library."""

from __future__ import annotations

import logging
from pathlib import Path

from reelforge.providers.base import AudioAsset, TTSProvider

logger = logging.getLogger(__name__)


class CoquiTTS(TTSProvider):
    """TTS provider using Coqui TTS (the 'TTS' library)."""

    def __init__(
        self,
        model_name: str = "tts_models/en/ljspeech/tacotron2-DDC",
        **kwargs,
    ) -> None:
        self.model_name = model_name
        self._tts = None

    def _get_tts(self):
        if self._tts is None:
            try:
                from TTS.api import TTS as CoquiTTSApi
            except ImportError:
                raise ImportError(
                    "The 'TTS' package is required for Coqui TTS. "
                    "Install it with: pip install TTS"
                )
            self._tts = CoquiTTSApi(model_name=self.model_name)
            logger.info("Coqui TTS model loaded: %s", self.model_name)
        return self._tts

    def synthesise(self, text: str, voice_profile: dict) -> AudioAsset:
        """Synthesise speech from text using Coqui TTS."""
        tts = self._get_tts()
        output_path = voice_profile.get("output_path", "audio.wav")
        speed = voice_profile.get("speed", 1.0)

        logger.info("Synthesising %d characters with Coqui TTS", len(text))

        tts.tts_to_file(
            text=text,
            file_path=output_path,
            speed=speed,
        )

        # Get duration from the generated file
        import wave
        duration = 0.0
        try:
            with wave.open(output_path, "rb") as wf:
                frames = wf.getnframes()
                rate = wf.getframerate()
                duration = frames / float(rate)
        except Exception:
            pass

        logger.info("Audio saved: %s (%.1fs)", output_path, duration)
        return AudioAsset(path=str(output_path), duration_seconds=duration)
