"""Interactive brand identity creation wizard."""

from __future__ import annotations

import logging
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

from reelforge.agent.brand import BrandIdentity
from reelforge.providers.base import (
    BrandIdentityData,
    Persona,
    Tone,
    VisualStyle,
    VoiceProfile,
)

logger = logging.getLogger(__name__)
console = Console()


def _ask(label: str, default: str = "") -> str:
    if default:
        return Prompt.ask(f"  {label}", default=default)
    return Prompt.ask(f"  {label}")


def _ask_list(label: str, hint: str = "comma-separated") -> list[str]:
    raw = Prompt.ask(f"  {label} ({hint})", default="")
    if not raw.strip():
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def run_wizard(brands_dir: Path) -> BrandIdentity:
    """Run the interactive brand creation wizard."""
    console.print()
    console.print(Panel(
        "[bold cyan]ReelForge Brand Identity Wizard[/]\n"
        "Answer the questions below to define your content creator persona.",
        border_style="cyan",
    ))
    console.print()

    # Basic info
    console.print("[bold]1. Basic Identity[/]")
    name = _ask("Brand name (used as folder name, no spaces)")
    if not name:
        console.print("[red]Brand name is required.[/]")
        return

    # Persona
    console.print("\n[bold]2. Persona[/]")
    character = _ask("Who is this creator?", "A knowledgeable tech enthusiast")
    speaks_as = _ask("Speaking style", "first person, direct and engaging")
    always_does = _ask_list("Rules to always follow", "comma-separated")
    never_does = _ask_list("Things to never do", "comma-separated")

    # Tone
    console.print("\n[bold]3. Tone & Voice[/]")
    voice = _ask("Voice/tone", "enthusiastic but grounded")
    reading_pace = Prompt.ask(
        "  Reading pace",
        choices=["slow", "medium", "fast"],
        default="medium",
    )
    vocabulary = _ask("Vocabulary level", "conversational")

    # Visual style
    console.print("\n[bold]4. Visual Style[/]")
    aesthetic = _ask("Visual aesthetic", "modern, clean, dark theme")
    colours = _ask_list("Colour palette (hex codes)", "e.g. #1a1a2e,#0f3460,#e94560")
    caption_style = Prompt.ask(
        "  Caption style",
        choices=["word_by_word", "sentence", "none"],
        default="word_by_word",
    )
    image_prompt_prefix = _ask(
        "Image prompt prefix (prepended to all image generation prompts)",
        "",
    )

    # Voice profile
    console.print("\n[bold]5. Voice Profile[/]")
    tts_provider = Prompt.ask(
        "  TTS provider",
        choices=["kokoro", "coqui"],
        default="kokoro",
    )
    voice_id = _ask("Voice ID", "af_heart")
    speed = float(Prompt.ask("  Speed", default="1.0"))
    pitch_adjust = float(Prompt.ask("  Pitch adjustment", default="0.0"))

    # Build the data model
    data = BrandIdentityData(
        name=name,
        persona=Persona(
            character=character,
            speaks_as=speaks_as,
            always_does=always_does,
            never_does=never_does,
        ),
        tone=Tone(
            voice=voice,
            reading_pace=reading_pace,
            vocabulary=vocabulary,
        ),
        visual_style=VisualStyle(
            aesthetic=aesthetic,
            colour_palette=colours,
            caption_style=caption_style,
            image_prompt_prefix=image_prompt_prefix,
        ),
        voice_profile=VoiceProfile(
            provider=tts_provider,
            voice_id=voice_id,
            speed=speed,
            pitch_adjust=pitch_adjust,
        ),
    )

    # Preview
    console.print()
    console.print(Panel(
        data.model_dump_json(indent=2),
        title=f"Brand: {name}",
        border_style="green",
    ))

    if Confirm.ask("\nSave this brand?", default=True):
        brand = BrandIdentity.save(brands_dir, data)
        console.print(f"\n[bold green]Brand '{name}' saved to {brand.brand_dir}[/]")
        return brand
    else:
        console.print("[yellow]Brand creation cancelled.[/]")
        return None
