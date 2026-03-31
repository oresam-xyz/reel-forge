# ReelForge

A pluggable, stateful AI agent that generates faceless short-form video content (reels/shorts).

## Architecture

ReelForge has two layers:

1. **Brand Identity Layer** — persistent profiles that define the content creator persona, tone, visual style, and voice
2. **Agent Pipeline** — a 6-phase stateful, resumable pipeline that produces a video for a given topic

### Pipeline Phases

| Phase | Description |
|-------|-------------|
| Research | Web research via DuckDuckGo, summarised by LLM |
| Planning | LLM generates a structured content plan |
| Review | Human-in-the-loop: approve, edit, or regenerate the plan |
| Script | LLM writes the full narration script |
| Assets | Voice (TTS) + visuals (image gen/stock) generated in parallel |
| Render | FFmpeg composites images + audio + word-by-word captions |

The pipeline is **resumable** — if it fails or is interrupted, run `reelforge resume` to pick up where it left off.

## Setup

```bash
pip install -r requirements.txt
```

Install optional provider dependencies based on your config:

```bash
# For Kokoro TTS
pip install kokoro soundfile

# For FLUX.1 image generation
pip install diffusers torch

# For Claude LLM
pip install anthropic
```

Copy and edit the config:

```bash
cp config.example.yaml config.yaml
```

## Usage

### Create a brand

```bash
reelforge brand create
```

This launches an interactive wizard to define your creator persona, tone, visual style, and voice profile.

### List brands

```bash
reelforge brand list
```

### Create a new video

```bash
reelforge new --topic "5 AI tools you need in 2025" --brand example_brand
```

### Resume a failed/interrupted project

```bash
reelforge resume --project 2025-01-15_5-ai-tools-you-need-in-2025
```

### Check project status

```bash
reelforge status --project 2025-01-15_5-ai-tools-you-need-in-2025
```

## Provider System

ReelForge uses pluggable providers. Configure them in `config.yaml`:

| Category | Providers | Notes |
|----------|-----------|-------|
| LLM | `ollama`, `claude` | Ollama for local, Claude for API |
| TTS | `kokoro`, `coqui` | Both run locally |
| Visuals | `flux`, `pexels` | Flux for AI images, Pexels for stock |
| Renderer | `ffmpeg` | Requires FFmpeg installed |

## Project Structure

```
reelforge/
├── agent/         # Pipeline runner, project state, brand loader, phases
├── providers/     # Abstract bases + concrete implementations
├── cli/           # Typer CLI + brand wizard
└── config.py      # YAML config loader
brands/            # Brand identity profiles
projects/          # Generated project outputs (gitignored)
```

## License

MIT
