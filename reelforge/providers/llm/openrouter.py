"""OpenRouter LLM provider — OpenAI-compatible API with access to multiple models."""

from __future__ import annotations

import json
import logging

import httpx

from reelforge.providers.base import LLMProvider

logger = logging.getLogger(__name__)

_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"
MAX_JSON_RETRIES = 2


class OpenRouterLLM(LLMProvider):
    """LLM provider using the OpenRouter API (OpenAI-compatible)."""

    def __init__(
        self,
        model: str = "anthropic/claude-haiku-4-5",
        api_key: str = "",
        **kwargs,
    ) -> None:
        self.model = model
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "https://oresam.xyz",
            "Content-Type": "application/json",
        }
        self._client = httpx.Client(timeout=120.0)

    def _chat(self, messages: list[dict], json_mode: bool = False) -> str:
        payload: dict = {"model": self.model, "messages": messages}
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        logger.debug("OpenRouter request: model=%s, messages=%d", self.model, len(messages))
        resp = self._client.post(_BASE_URL, json=payload, headers=self._headers)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    def generate(self, prompt: str, system: str = "") -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return self._chat(messages)

    def generate_json(self, prompt: str, system: str = "") -> dict:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        last_error = ""
        for attempt in range(1, MAX_JSON_RETRIES + 1):
            if last_error:
                messages[-1]["content"] = (
                    f"{prompt}\n\n"
                    f"Your previous response was invalid JSON. Error: {last_error}\n"
                    f"Respond ONLY with valid JSON."
                )

            logger.debug("OpenRouter JSON request attempt %d/%d", attempt, MAX_JSON_RETRIES)
            raw = self._chat(messages, json_mode=True)

            # Strip markdown fences if present
            text = raw.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

            try:
                return json.loads(text)
            except json.JSONDecodeError as e:
                last_error = str(e)
                logger.warning("OpenRouter JSON parse failed (attempt %d): %s", attempt, last_error)

        raise ValueError(
            f"OpenRouter failed to produce valid JSON after {MAX_JSON_RETRIES} attempts: {last_error}"
        )

    def close(self) -> None:
        self._client.close()
