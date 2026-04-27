# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Running locally

```bash
# Backend (FastAPI, port 8001)
uvicorn webapp.api.main:app --reload --port 8001

# Frontend dev server (port 5173, proxies /api and /auth to :8001)
cd webapp/frontend && npm run dev

# Build frontend for production
cd webapp/frontend && npm run build
```

Requires `config.yaml` in repo root (copy from `config.example.yaml`).
Requires `.env` with `DATABASE_URL`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `OPENROUTER_API_KEY`, `FAL_KEY`, `SECRET_KEY`, `ALLOWED_EMAILS`, `FRONTEND_URL`.

## Production

- **URL:** forge.oresam.xyz
- **Server:** 49.12.118.188 (root SSH), deployed to `/opt/reel-forge`
- **Systemd service:** `reel-forge` — runs uvicorn on `127.0.0.1:8001`, nginx proxies it
- **Deploy:** run `/deploy` from this directory

## Architecture

### Webapp layer (`webapp/`)

**Backend** — FastAPI app in `webapp/api/main.py` with routes:

| Route file | Prefix | Purpose |
|------------|--------|---------|
| `chat.py` | `/api/chat` | Conversational assistant (brand + campaign creation) |
| `campaigns.py` | `/api/campaigns` | Campaign CRUD |
| `jobs.py` | `/api/jobs` | Job status, approval, output |
| `brands.py` | `/api/brands` | Brand identity CRUD |
| `me.py` | `/api/me` | Auth user settings |

**Frontend** — Vue 3 + TypeScript SPA in `webapp/frontend/src/`:

| View | Route | Purpose |
|------|-------|---------|
| `ChatView.vue` | `/` | Chat assistant — default landing page |
| `CampaignsView.vue` | `/campaigns` | Campaign list |
| `CampaignView.vue` | `/campaigns/:id` | Campaign detail + job list |
| `JobView.vue` | `/jobs/:id` | Job status + video output |
| `SettingsView.vue` | `/settings` | User + brand settings |

**Database** — PostgreSQL, schema in `webapp/db/schema.sql` (idempotent, run to migrate):

| Table | Purpose |
|-------|---------|
| `users` | Google OAuth users |
| `campaigns` | Campaign briefs (brand_name, brief JSON, auto_approve) |
| `jobs` | Pipeline jobs (status, phase, cost_usd, output_path) |
| `chat_sessions` | Per-brand conversation history + cost tracking |

**Worker** — `webapp/worker/runner.py` picks up `pending` jobs and drives the pipeline. Runs in the same process as the API (startup event), polls every few seconds.

### Chat assistant (`webapp/api/routes/chat.py`)

Uses OpenRouter (claude-haiku-4-5) with tool use. Tool loop:

1. `list_brands` — fetch existing brands
2. `create_brand` — write `brands/{name}/identity.json`
3. `create_campaign` — insert into `campaigns` table
4. `suggest_angles` — LLM generates 3–5 angles for the campaign
5. `queue_jobs` — insert `pending` jobs for selected angles

Conversation persisted in `chat_sessions` (JSONB). Token costs tracked at $0.80/$4.00 per 1M input/output (haiku-4-5).

### Pipeline engine (`reelforge/`)

6-phase pipeline, one phase per file in `reelforge/agent/phases/`:

1. `research.py` — DuckDuckGo + LLM summarise → `research.json`
2. `planning.py` — LLM generates `ContentPlan` → `plan.json`
3. `review.py` — interactive approval or auto-approve → updates `plan.json`
4. `script.py` — LLM writes narration + visual prompts → `assets/script.json`
5. `assets.py` — TTS audio then video clips → `assets/audio.wav`, `assets/clip_*.mp4`
6. `render.py` — Whisper captions + FFmpeg composite → `output.mp4`

`reelforge/agent/runner.py` — iterates phases, skips completed, marks failures in `state.json`.

Each job maps to a directory under `projects/` (path stored as `jobs.project_id`). `Project` in `reelforge/agent/project.py` manages state and artifact I/O.

### Provider system

Abstract bases in `reelforge/providers/base.py`. Config-driven: `config.yaml` → `ProviderConfig` (Pydantic, `extra="allow"`) → `instantiate_providers()` in `runner.py`.

Current production config: openrouter LLM, kokoro TTS, fal.ai (kling-2.6-pro) visuals, ffmpeg renderer.

## Key files

```
webapp/api/main.py              # FastAPI app, router registration, startup
webapp/api/routes/chat.py       # Chat assistant, tool loop, session persistence
webapp/db/schema.sql            # Full DB schema (idempotent)
webapp/frontend/src/views/      # All Vue page components
webapp/frontend/src/api/        # Typed API clients
webapp/worker/runner.py         # Job queue poller
reelforge/agent/runner.py       # Pipeline orchestrator
reelforge/agent/phases/         # One file per pipeline phase
reelforge/providers/            # LLM, TTS, visuals, renderer implementations
config.yaml                     # Provider config (gitignored)
```

## Common tasks

**Add a new API route:**
1. Create `webapp/api/routes/myroute.py` with an `APIRouter`
2. Import and register in `webapp/api/main.py`

**Add a pipeline phase:**
1. Add a module to `reelforge/agent/phases/` with a `run(project, brand, providers)` function
2. Insert into `PHASES` list in `reelforge/agent/runner.py`

**Run DB migrations:**
```bash
psql $DATABASE_URL < webapp/db/schema.sql
```

**Check job logs on server:**
```bash
ssh root@49.12.118.188 "journalctl -u reel-forge -f"
```
