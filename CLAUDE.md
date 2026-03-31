# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the Project

```bash
# CLI commands (run from repo root)
python3 -m reelforge.cli.main new --topic "topic" --brand example_brand
python3 -m reelforge.cli.main resume --project <project_id>
python3 -m reelforge.cli.main status --project <project_id>
python3 -m reelforge.cli.main brand create
python3 -m reelforge.cli.main brand list

# MCP server (stdio JSON-RPC, used by AI agents)
python3 -m reelforge.mcp_server
# Set REELFORGE_ROOT env var to override working directory
```

Requires `config.yaml` in the working directory (copy from `config.example.yaml`). Requires Ollama running locally with the configured model.

## Architecture

### Two-Layer Design

**Brand Identity Layer**: Persistent JSON profiles in `brands/{name}/identity.json` defining persona, tone, visual style, and voice. Loaded by `BrandIdentity` in `reelforge/agent/brand.py`.

**Agent Pipeline**: 6 sequential phases, each a module in `reelforge/agent/phases/` with a `run(project, brand, providers)` function:

1. **research** — DuckDuckGo search + LLM summarization → `research.json`
2. **planning** — LLM generates content plan → `plan.json`
3. **review** — Interactive approval (CLI) or auto-approve (MCP) → updates `plan.json`
4. **script** — LLM writes narration + visual prompts → `assets/script.json`
5. **assets** — TTS audio then visual clips sequentially (GPU shared) → `assets/audio.wav` + `assets/clip_*.mp4`
6. **render** — Whisper captions + FFmpeg composite → `output.mp4`

### Pipeline Execution

`reelforge/agent/runner.py` orchestrates phases. `run_pipeline()` iterates PHASES, skips completed ones, marks failures in state. Accepts `phase_overrides` dict to substitute phase functions (used by MCP server to replace interactive review with auto-approve).

Each project is a directory under `projects/` with `state.json` tracking phase statuses. `Project` class in `reelforge/agent/project.py` manages all state and artifact I/O.

### Provider System

Abstract bases in `reelforge/providers/base.py`: `LLMProvider`, `TTSProvider`, `VisualProvider`, `RendererProvider`. Concrete implementations in subdirectories. `Providers` dataclass bundles all four.

Provider instantiation is config-driven: `config.yaml` → `ProviderConfig` (Pydantic, allows extra fields) → `instantiate_providers()` in runner.py uses lazy imports and passes extra config as kwargs.

All GPU-using providers (Kokoro, AnimateDiff, Wan) have a `release()` method that frees VRAM. The assets phase calls release between TTS and visuals, and after visuals before render.

### MCP Server

`reelforge/mcp_server.py` uses [minimcp](../minimcp) to expose 8 tools over stdio JSON-RPC. Tools are sync functions (minimcp runs them in executor). Config/providers are lazy-loaded singletons. Review phase is handled via `phase_overrides` — auto-approve or stop-before-review for agent-driven workflows.

### Data Models

All in `reelforge/providers/base.py` as Pydantic models: `BrandIdentityData`, `ContentPlan`, `Script`, `CaptionData`, `ProjectState`, `PhaseInfo`, plus asset types (`AudioAsset`, `VisualAsset`, `SegmentBrief`).

## GPU Memory Constraints

This system runs on an AMD RX 6600 (8GB VRAM shared with display, ~2.8GB free for PyTorch). Key implications:

- GPU models load one at a time: TTS → release → visuals → release → Whisper
- AnimateDiff uses `enable_sequential_cpu_offload()` + `enable_attention_slicing("auto")` — direct `.to("cuda")` won't fit
- `enable_model_cpu_offload()` has a meta tensor bug on this PyTorch/ROCm combo — don't use it
- AnimateDiff maxes out at 256x256 / 8 frames on this GPU
- Wan2.1 text encoder (22GB) must run on CPU — impractically slow

## Config

`config.yaml` (gitignored) defines providers and their settings. `ProviderConfig` uses `extra="allow"` so any provider-specific fields pass through as kwargs. Environment variables supported via `env:VAR_NAME` syntax.
