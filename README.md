# Reel-Forge

AI-powered short-form video factory. Create faceless 9:16 video ads through a conversational web interface — define a brand, set up a campaign, and the pipeline handles research, scripting, voiceover, video generation, and rendering.

**Live at:** [forge.oresam.xyz](https://forge.oresam.xyz)

---

## Architecture

Reel-Forge has two layers:

### Web Application (`webapp/`)

| Component | Stack |
|-----------|-------|
| Frontend | Vue 3 + TypeScript + Vite |
| Backend | FastAPI + PostgreSQL |
| Auth | Google OAuth |
| Worker | Background job runner (same process) |

The default route is the **chat interface** — a conversational assistant that walks you through brand creation and campaign setup. Once a campaign exists and jobs are queued, the pipeline runs and produces output videos.

### Pipeline Engine (`reelforge/`)

6-phase stateful pipeline that produces one video per job:

| Phase | Output |
|-------|--------|
| Research | Web research via DuckDuckGo, summarised by LLM |
| Planning | Structured content plan (`plan.json`) |
| Review | Human approval via webapp or auto-approve |
| Script | Narration + visual prompts per segment |
| Assets | Voice (TTS) + video clips |
| Render | FFmpeg composite → `output.mp4` |

The pipeline is **resumable** — if interrupted, it picks up from the last completed phase.

---

## Setup

### Requirements

- Python 3.12+
- Node.js 18+
- PostgreSQL
- FFmpeg

### Install

```bash
pip install -r requirements.txt

# Kokoro TTS (local, free)
pip install kokoro soundfile

cd webapp/frontend && npm install
```

### Configure

```bash
cp config.example.yaml config.yaml
```

Edit `config.yaml` with your provider keys. Minimum viable config:

```yaml
providers:
  llm:
    provider: openrouter
    model: anthropic/claude-haiku-4-5
    api_key: env:OPENROUTER_API_KEY
  tts:
    provider: kokoro
    voice_id: af_heart
  visuals:
    provider: falai
    model: kling-2.6-pro
    api_key: env:FAL_KEY
  renderer:
    provider: ffmpeg
```

Create a `.env` in the project root:

```bash
DATABASE_URL=postgresql://user:pass@localhost/reelforge
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
OPENROUTER_API_KEY=...
FAL_KEY=...
SECRET_KEY=<random 32-char string>
ALLOWED_EMAILS=you@example.com
FRONTEND_URL=http://localhost:5173
```

### Run locally

```bash
# Start backend (port 8001)
uvicorn webapp.api.main:app --reload --port 8001

# Start frontend dev server (port 5173)
cd webapp/frontend && npm run dev
```

### Run the database migrations

Migrations are idempotent — run the schema on first setup and after any update:

```bash
psql $DATABASE_URL < webapp/db/schema.sql
```

---

## Provider System

Configure in `config.yaml`. All providers are pluggable.

| Category | Provider | Notes |
|----------|----------|-------|
| LLM | `openrouter` | Recommended — routes to Claude, GPT, etc. |
| LLM | `ollama` | Local models (e.g. llama3.2) |
| TTS | `kokoro` | Local, free. Voice IDs: `af_heart`, `af_sky`, `bf_emma`, `bf_isabella`, `am_adam`, `bm_george` |
| TTS | `elevenlabs` | Cloud API |
| Visuals | `falai` | fal.ai API — Kling 2.6 Pro recommended |
| Visuals | `pexels` | Free stock video (no AI generation) |
| Visuals | `animatediff` | Local GPU (requires ROCm/CUDA) |
| Renderer | `ffmpeg` | Required, CPU-only |

---

## Chat Assistant

The conversational assistant at `/` handles the full onboarding flow:

1. **Create brand** — define persona, tone, visual style, voice
2. **Create campaign** — product, audience, pain point, CTA
3. **Suggest angles** — LLM generates 3–5 video angle options
4. **Queue jobs** — selected angles queued as pipeline jobs

Conversation history is persisted per brand in the `chat_sessions` table. Token costs are tracked and attributed to each session.

---

## Project Structure

```
reelforge/           # Pipeline engine
├── agent/           # Runner, project state, brand loader, phases
├── providers/       # Abstract bases + implementations (LLM, TTS, visuals, renderer)
├── cli/             # Typer CLI (brand wizard, run/resume/status)
└── config.py        # YAML config loader

webapp/              # Web application
├── api/             # FastAPI app + routes (chat, campaigns, jobs, brands, me)
├── db/              # schema.sql + database connection
├── frontend/        # Vue 3 + Vite SPA
└── worker/          # Background job runner

brands/              # Brand identity profiles (gitignored on server)
projects/            # Pipeline output (gitignored)
config.yaml          # Provider config (gitignored)
```

---

## License

MIT
