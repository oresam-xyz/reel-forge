"""ElevenLabs TTS provider — cloud text-to-speech via the ElevenLabs REST API."""

from __future__ import annotations

import logging
import subprocess
import tempfile
from pathlib import Path

import httpx

from reelforge.providers.base import AudioAsset, TTSProvider

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.elevenlabs.io/v1"
_DEFAULT_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"  # Rachel — neutral, clear


class ElevenLabsTTS(TTSProvider):
    """TTS provider using the ElevenLabs cloud API."""

    def __init__(
        self,
        api_key: str = "",
        voice_id: str = _DEFAULT_VOICE_ID,
        **kwargs,
    ) -> None:
        self._api_key = api_key
        self._default_voice_id = voice_id
        self._client = httpx.Client(timeout=60.0)

    def synthesise(self, text: str, voice_profile: dict) -> AudioAsset:
        voice_id = voice_profile.get("voice_id") or self._default_voice_id
        speed = float(voice_profile.get("speed", 1.0))

        url = f"{_BASE_URL}/text-to-speech/{voice_id}"
        payload = {
            "text": text,
            "model_id": "eleven_turbo_v2",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75,
                "speed": speed,
            },
        }
        headers = {
            "xi-api-key": self._api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        }

        logger.info("ElevenLabs TTS: voice=%s, key_prefix=%s, text_length=%d", voice_id, self._api_key[:8] if self._api_key else "EMPTY", len(text))
        resp = self._client.post(url, json=payload, headers=headers)
        if not resp.is_success:
            logger.error("ElevenLabs error %d: %s", resp.status_code, resp.text[:300])
        resp.raise_for_status()

        # Save MP3 to temp, then convert to WAV at output_path if requested
        tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        tmp.write(resp.content)
        tmp.close()

        output_path = voice_profile.get("output_path")
        if output_path:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                ["ffmpeg", "-nostdin", "-y", "-i", tmp.name, str(output_path)],
                check=True,
                capture_output=True,
            )
            Path(tmp.name).unlink(missing_ok=True)
            return AudioAsset(path=str(output_path), duration_seconds=0.0)

        return AudioAsset(path=tmp.name, duration_seconds=0.0)

    def release(self) -> None:
        pass  # no GPU resources to free

    def close(self) -> None:
        self._client.close()
