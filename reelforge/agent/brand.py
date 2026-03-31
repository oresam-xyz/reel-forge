"""BrandIdentity — loads and validates brand identity.json files."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from reelforge.providers.base import BrandIdentityData

logger = logging.getLogger(__name__)

BRAND_SYSTEM_TEMPLATE = """\
You are {character}.

Speaking style: {speaks_as}
Tone: {voice} | Pace: {reading_pace} | Vocabulary: {vocabulary}
Visual aesthetic: {aesthetic}

Rules you ALWAYS follow:
{always_rules}

Rules you NEVER break:
{never_rules}
"""


class BrandIdentity:
    """Wrapper around BrandIdentityData with file I/O and prompt generation."""

    def __init__(self, data: BrandIdentityData, brand_dir: Path) -> None:
        self.data = data
        self.brand_dir = brand_dir

    @classmethod
    def load(cls, brands_dir: Path, name: str) -> BrandIdentity:
        """Load a brand from brands/{name}/identity.json."""
        brand_dir = brands_dir / name
        identity_path = brand_dir / "identity.json"
        if not identity_path.exists():
            raise FileNotFoundError(
                f"Brand '{name}' not found at {identity_path}"
            )
        raw = json.loads(identity_path.read_text())
        data = BrandIdentityData.model_validate(raw)
        logger.info("Loaded brand '%s'", name)
        return cls(data, brand_dir)

    @classmethod
    def save(cls, brands_dir: Path, data: BrandIdentityData) -> BrandIdentity:
        """Save a new brand identity to disk."""
        brand_dir = brands_dir / data.name
        brand_dir.mkdir(parents=True, exist_ok=True)
        identity_path = brand_dir / "identity.json"
        identity_path.write_text(data.model_dump_json(indent=2))
        logger.info("Saved brand '%s' to %s", data.name, brand_dir)
        return cls(data, brand_dir)

    @property
    def system_prompt(self) -> str:
        """Format brand data into an LLM system prompt."""
        d = self.data
        always_rules = "\n".join(f"- {r}" for r in d.persona.always_does) or "- (none)"
        never_rules = "\n".join(f"- {r}" for r in d.persona.never_does) or "- (none)"
        return BRAND_SYSTEM_TEMPLATE.format(
            character=d.persona.character,
            speaks_as=d.persona.speaks_as,
            voice=d.tone.voice,
            reading_pace=d.tone.reading_pace,
            vocabulary=d.tone.vocabulary,
            aesthetic=d.visual_style.aesthetic,
            always_rules=always_rules,
            never_rules=never_rules,
        )

    @classmethod
    def list_brands(cls, brands_dir: Path) -> list[tuple[str, str]]:
        """Return list of (name, character) for all brands."""
        results = []
        if not brands_dir.exists():
            return results
        for brand_dir in sorted(brands_dir.iterdir()):
            identity_path = brand_dir / "identity.json"
            if identity_path.exists():
                try:
                    raw = json.loads(identity_path.read_text())
                    data = BrandIdentityData.model_validate(raw)
                    results.append((data.name, data.persona.character))
                except Exception:
                    results.append((brand_dir.name, "(invalid identity.json)"))
        return results
