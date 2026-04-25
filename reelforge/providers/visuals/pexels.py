"""Pexels visual provider — stock footage/images from the Pexels API."""

from __future__ import annotations

import logging
import re
from pathlib import Path

import httpx

from reelforge.providers.base import SegmentBrief, VisualAsset, VisualProvider

logger = logging.getLogger(__name__)

PEXELS_SEARCH_URL = "https://api.pexels.com/v1/search"

# Words that are visual-direction jargon, not useful as Pexels search terms
_DIRECTION_WORDS = {
    "split", "screen", "cut", "close-up", "closeup", "wide", "shot", "montage",
    "overlay", "text", "animation", "fade", "zoom", "pan", "tilt", "b-roll",
    "broll", "shows", "showing", "depicting", "scene", "visual", "footage",
    "left", "right", "side", "foreground", "background", "transition",
    "appears", "appearing", "represented", "symbolized", "displayed",
}


def _pexels_query(visual_brief: str) -> str:
    """Extract a clean 4-6 word Pexels search query from a visual brief."""
    # Take only the first sentence or clause
    first = re.split(r"[.!?;]", visual_brief)[0]
    # Strip any "Directive: content" prefix
    if ":" in first:
        first = first.split(":", 1)[-1]
    # Remove parenthetical asides
    first = re.sub(r"\([^)]*\)", "", first)
    # Tokenise and drop direction jargon + short filler words
    words = re.findall(r"[a-zA-Z]+", first.lower())
    filtered = [
        w for w in words
        if w not in _DIRECTION_WORDS and len(w) > 2
    ]
    return " ".join(filtered[:5])


class PexelsVisual(VisualProvider):
    """Visual provider using the Pexels stock photo API."""

    def __init__(
        self,
        pexels_api_key: str = "",
        output_dir: str = ".",
        orientation: str = "portrait",
        size: str = "large",
        **kwargs,
    ) -> None:
        if not pexels_api_key:
            raise ValueError("Pexels API key is required. Set pexels_api_key in config.")
        self.api_key = pexels_api_key
        self.output_dir = output_dir
        self.orientation = orientation
        self.size = size
        self._client = httpx.Client(
            timeout=30.0,
            headers={"Authorization": self.api_key},
        )

    def get_visuals(
        self, segments: list[SegmentBrief], style: dict
    ) -> list[VisualAsset]:
        """Search and download one stock image per segment from Pexels."""
        output_dir = Path(style.get("output_dir", self.output_dir))
        output_dir.mkdir(parents=True, exist_ok=True)

        assets = []
        for seg in segments:
            query = _pexels_query(seg.visual_brief) or seg.visual_brief[:60]
            output_path = output_dir / f"img_{seg.segment_id:02d}.png"

            logger.info("Searching Pexels for segment %d: %s", seg.segment_id, query[:60])

            resp = self._client.get(
                PEXELS_SEARCH_URL,
                params={
                    "query": query,
                    "per_page": 1,
                    "orientation": self.orientation,
                    "size": self.size,
                },
            )
            resp.raise_for_status()
            data = resp.json()

            photos = data.get("photos", [])
            if not photos:
                logger.warning("No Pexels results for: %s", query[:60])
                continue

            photo = photos[0]
            # Get the large2x or original URL
            image_url = photo.get("src", {}).get("large2x") or photo.get("src", {}).get("original", "")

            if not image_url:
                logger.warning("No image URL found for segment %d", seg.segment_id)
                continue

            # Download the image
            logger.info("Downloading image from Pexels: %s", image_url[:80])
            img_resp = self._client.get(image_url)
            img_resp.raise_for_status()
            output_path.write_bytes(img_resp.content)

            logger.info("Image saved: %s", output_path)
            assets.append(VisualAsset(
                path=str(output_path),
                segment_id=seg.segment_id,
                type="image",
            ))

        return assets
