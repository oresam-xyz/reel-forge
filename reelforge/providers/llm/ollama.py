"""Ollama LLM provider — talks to a local Ollama instance via REST API."""

from __future__ import annotations

import json
import logging

import httpx

from reelforge.providers.base import LLMProvider

logger = logging.getLogger(__name__)

MAX_JSON_RETRIES = 2


class OllamaLLM(LLMProvider):
    """LLM provider using a local Ollama server."""

    def __init__(
        self,
        model: str = "llama3.2",
        base_url: str = "http://localhost:11434",
        **kwargs,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self._client = httpx.Client(timeout=180.0)

    def generate(self, prompt: str, system: str = "") -> str:
        """Generate a free-form text response from Ollama."""
        payload: dict = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
        }
        if system:
            payload["system"] = system

        logger.debug("Ollama request: model=%s, prompt length=%d", self.model, len(prompt))
        resp = self._client.post(f"{self.base_url}/api/generate", json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data.get("response", "")

    def generate_json(self, prompt: str, system: str = "") -> dict:
        """Generate a JSON response from Ollama using its JSON mode."""
        payload: dict = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
        }
        if system:
            payload["system"] = system

        last_error = ""
        for attempt in range(1, MAX_JSON_RETRIES + 1):
            actual_prompt = prompt
            if last_error:
                actual_prompt = (
                    f"{prompt}\n\n"
                    f"Your previous response was invalid JSON. Error: {last_error}\n"
                    f"Please respond ONLY with valid JSON."
                )
                payload["prompt"] = actual_prompt

            logger.debug("Ollama JSON request attempt %d/%d", attempt, MAX_JSON_RETRIES)
            resp = self._client.post(f"{self.base_url}/api/generate", json=payload)
            resp.raise_for_status()
            raw_text = resp.json().get("response", "")

            try:
                return json.loads(raw_text)
            except json.JSONDecodeError as e:
                last_error = str(e)
                logger.warning(
                    "Ollama JSON parse failed (attempt %d): %s", attempt, last_error
                )

        raise ValueError(
            f"Ollama failed to produce valid JSON after {MAX_JSON_RETRIES} attempts: {last_error}"
        )
