"""OpenRouter LLM provider — OpenAI-compatible API with access to multiple models."""

from __future__ import annotations

import json
import logging

import httpx

from reelforge.providers.base import LLMProvider, raise_if_credit_error

logger = logging.getLogger(__name__)

_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"
MAX_JSON_RETRIES = 2

_TOKEN_PRICES = {
    "anthropic/claude-haiku-4-5": (0.80, 4.00),
    "anthropic/claude-haiku-4-5-20251001": (0.80, 4.00),
    "anthropic/claude-sonnet-4-5": (3.00, 15.00),
    "anthropic/claude-opus-4-5": (15.00, 75.00),
}
_DEFAULT_TOKEN_PRICE = (1.00, 5.00)


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
        self.cost_usd: float = 0.0

    def _chat(self, messages: list[dict], json_mode: bool = False) -> str:
        payload: dict = {"model": self.model, "messages": messages}
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        logger.debug("OpenRouter request: model=%s, messages=%d", self.model, len(messages))
        resp = self._client.post(_BASE_URL, json=payload, headers=self._headers)
        raise_if_credit_error(resp, "OpenRouter")
        resp.raise_for_status()
        data = resp.json()
        usage = data.get("usage", {})
        if usage:
            input_tokens = usage.get("prompt_tokens", 0)
            output_tokens = usage.get("completion_tokens", 0)
            input_price, output_price = _TOKEN_PRICES.get(self.model, _DEFAULT_TOKEN_PRICE)
            self.cost_usd += (input_tokens * input_price + output_tokens * output_price) / 1_000_000
        return data["choices"][0]["message"]["content"]

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
