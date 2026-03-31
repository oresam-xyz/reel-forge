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
| Assets | Voice (TTS) + visuals (video clips) generated sequentially |
| Render | FFmpeg composites clips + audio + word-by-word captions |

The pipeline is **resumable** — if it fails or is interrupted, run `reelforge resume` to pick up where it left off.

## Setup

```bash
pip install -r requirements.txt
```

Install optional provider dependencies based on your config:

```bash
# For Kokoro TTS
pip install kokoro soundfile

# For AnimateDiff / Wan video generation
pip install diffusers torch

# For Claude LLM
pip install anthropic

# For MCP server
pip install minimcp
# Or from local source:
pip install -e /path/to/minimcp
```

Copy and edit the config:

```bash
cp config.example.yaml config.yaml
```

## Usage

### CLI

#### Create a brand

```bash
reelforge brand create
```

This launches an interactive wizard to define your creator persona, tone, visual style, and voice profile.

#### List brands

```bash
reelforge brand list
```

#### Create a new video

```bash
reelforge new --topic "5 AI tools you need in 2025" --brand example_brand
```

#### Resume a failed/interrupted project

```bash
reelforge resume --project 2025-01-15_5-ai-tools-you-need-in-2025
```

#### Check project status

```bash
reelforge status --project 2025-01-15_5-ai-tools-you-need-in-2025
```

### MCP Server

ReelForge exposes an MCP (Model Context Protocol) server so AI agents can create and manage videos programmatically.

#### Start the server

```bash
python3 -m reelforge.mcp_server
```

#### Configure in Claude Code

Add to `.mcp.json` in the project root (already included):

```json
{
  "mcpServers": {
    "reelforge": {
      "command": "python3",
      "args": ["-m", "reelforge.mcp_server"],
      "cwd": "/path/to/reel-forge"
    }
  }
}
```

Set `REELFORGE_ROOT` env var to override the working directory.

#### Available MCP Tools

| Tool | Parameters | Description |
|------|-----------|-------------|
| `create_brand` | `name`, `character`, + optional style/voice fields | Create a brand identity |
| `create_project` | `topic`, `brand` | Create a new video project |
| `run_pipeline` | `project_id`, `auto_approve` (default: true) | Run or resume the pipeline |
| `get_project_status` | `project_id` | Get phase-by-phase status |
| `list_projects` | — | List all projects with status |
| `list_brands` | — | List available brands |
| `get_plan` | `project_id` | Get the content plan for review |
| `approve_plan` | `project_id`, `approved`, `feedback` | Approve, edit, or reject a plan |

#### Agent-driven workflow

```
create_project("5 facts about dogs", "my_brand")
  → project_id

run_pipeline(project_id, auto_approve=false)
  → pauses at review

get_plan(project_id)
  → read the plan

approve_plan(project_id, approved=true, feedback="make it funnier")
  → plan updated and approved

run_pipeline(project_id)
  → completes remaining phases → output.mp4
```

## Provider System

ReelForge uses pluggable providers. Configure them in `config.yaml`:

| Category | Providers | Notes |
|----------|-----------|-------|
| LLM | `ollama`, `claude` | Ollama for local, Claude for API |
| TTS | `kokoro`, `coqui` | Both run locally |
| Visuals | `animatediff`, `wan`, `flux`, `pexels` | AnimateDiff/Wan for AI video, Pexels for stock |
| Renderer | `ffmpeg` | Requires FFmpeg installed |

### GPU Notes

On GPUs with shared display (e.g. AMD RX 6600 with ~2.8GB free VRAM):
- TTS and visual generation run **sequentially**, not in parallel
- Each provider releases GPU memory before the next loads
- AnimateDiff uses sequential CPU offload + attention slicing
- AnimateDiff base model is configurable (default: `Lykon/dreamshaper-8` for better quality)

## Project Structure

```
reelforge/
├── agent/         # Pipeline runner, project state, brand loader, phases
├── providers/     # Abstract bases + concrete implementations
├── cli/           # Typer CLI + brand wizard
├── mcp_server.py  # MCP server for agent-driven workflows
└── config.py      # YAML config loader
brands/            # Brand identity profiles
projects/          # Generated project outputs (gitignored)
```

## License

MIT
