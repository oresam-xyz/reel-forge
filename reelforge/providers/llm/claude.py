"""Claude LLM provider — uses the Anthropic Python SDK."""

from __future__ import annotations

import json
import logging

from reelforge.providers.base import LLMProvider

logger = logging.getLogger(__name__)

MAX_JSON_RETRIES = 2


class ClaudeLLM(LLMProvider):
    """LLM provider using the Anthropic Messages API."""

    def __init__(
        self,
        model: str = "claude-sonnet-4-20250514",
        api_key: str = "",
        max_tokens: int = 4096,
        **kwargs,
    ) -> None:
        try:
            import anthropic
        except ImportError:
            raise ImportError(
                "The 'anthropic' package is required for the Claude provider. "
                "Install it with: pip install anthropic"
            )
        self.model = model
        self.max_tokens = max_tokens
        self._client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()

    def generate(self, prompt: str, system: str = "") -> str:
        """Generate a free-form text response from Claude."""
        kwargs: dict = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system

        logger.debug("Claude request: model=%s, prompt length=%d", self.model, len(prompt))
        message = self._client.messages.create(**kwargs)
        return message.content[0].text

    def generate_json(self, prompt: str, system: str = "") -> dict:
        """Generate a JSON response from Claude."""
        json_prompt = (
            f"{prompt}\n\n"
            "Respond ONLY with valid JSON. No markdown, no code fences, no explanation."
        )

        last_error = ""
        for attempt in range(1, MAX_JSON_RETRIES + 1):
            actual_prompt = json_prompt
            if last_error:
                actual_prompt = (
                    f"{json_prompt}\n\n"
                    f"Your previous response was invalid JSON. Error: {last_error}\n"
                    f"Please respond ONLY with valid JSON."
                )

            logger.debug("Claude JSON request attempt %d/%d", attempt, MAX_JSON_RETRIES)
            raw_text = self.generate(actual_prompt, system=system)

            # Strip markdown code fences if present
            text = raw_text.strip()
            if text.startswith("```"):
                lines = text.split("\n")
                lines = lines[1:]  # remove opening fence
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                text = "\n".join(lines)

            try:
                return json.loads(text)
            except json.JSONDecodeError as e:
                last_error = str(e)
                logger.warning(
                    "Claude JSON parse failed (attempt %d): %s", attempt, last_error
                )

        raise ValueError(
            f"Claude failed to produce valid JSON after {MAX_JSON_RETRIES} attempts: {last_error}"
        )
