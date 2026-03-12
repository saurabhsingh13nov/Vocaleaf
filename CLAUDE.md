# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Vocaleaf is a personalized children's storybook web app with AI-generated text, illustrations, and cloned parent voice narration.

## Tech Stack

- **Backend:** FastAPI (Python 3.12+), SQLAlchemy 2.0 (async), Alembic, uv
- **Frontend:** Vue 3 (Composition API) + Vite + Tailwind CSS + Pinia + TypeScript
- **Database:** PostgreSQL 16 (metadata only; no binary blobs)
- **Queue/Cache:** Celery + Redis 7
- **Auth:** JWT in HTTP-only cookies (access 15min + refresh 7d), Argon2id for passwords
- **Object storage:** Cloudflare R2 (S3-compatible, via boto3) — private buckets only
- **AI providers:** Claude (text), Google Imagen (images), ElevenLabs (voice cloning + TTS)
- **Production DB:** Supabase (managed Postgres)

## Local Development

```bash
# 1. Start infrastructure (Postgres + Redis)
docker compose up -d

# 2. Start backend (from project root)
cd backend
uv sync                                 # Install/update deps
uv run alembic upgrade head             # Run migrations
uv run uvicorn app.main:app --reload    # Start API on :8000

# 3. Start frontend (new terminal, from project root)
cd frontend
npm install                             # Install/update deps
npm run dev                             # Start dev server on :5173

# 4. Open http://localhost:5173

# Stop infrastructure
docker compose down
```

### Running Tests

```bash
# Backend
cd backend && uv run pytest
cd backend && uv run pytest tests/test_auth.py -k "test_login"  # Single test

# Frontend
cd frontend && npm run test:unit        # Vitest
cd frontend && npm run test:unit -- --run
cd frontend && npm run lint             # Lint
```

### Celery Worker (when needed, Phase 8+)

```bash
cd backend && uv run celery -A app.tasks.celery_app worker --loglevel=info
```

## Architecture

The system has three main execution contexts:

1. **FastAPI API** — validates input, persists metadata, enqueues work, returns quickly. Never blocks on AI generation.
2. **Background workers** — text worker (story outline + page text), image worker (illustrations), audio worker (TTS + voice cloning), post-process worker (thumbnails, cleanup).
3. **Orchestrator** — coordinates the full generation pipeline, dispatches page-level tasks, updates statuses.

**Asset access pattern:** Frontend requests signed URLs from FastAPI -> browser loads images/audio directly from object storage. Never stream media bytes through the API server.

**Upload pattern:** Frontend requests signed upload URL from FastAPI -> browser uploads directly to object storage -> frontend notifies backend -> backend creates `assets` row and domain rows.

## Key Docs (read before making changes)

| Topic | File |
|---|---|
| System design | `docs/architecture.md` |
| Data model / ER model | `docs/schema.md` |
| Auth / OAuth / sessions | `docs/auth.md` |
| Storage, signed URLs, asset model | `docs/storage.md` |
| Voice cloning lifecycle | `docs/voice.md` |
| Story generation pipeline | `docs/story-generation.md` |
| Full build plan | `docs/plans/2026-03-11-build-plan.md` |

**Rule:** If a relevant doc doesn't exist yet, create it before introducing major new code paths.

## Project Layout

```
backend/
  app/
    api/           # FastAPI route handlers
    core/          # Config, settings (pydantic-settings)
    db/            # Async SQLAlchemy session, Base
    models/        # SQLAlchemy ORM models
    schemas/       # Pydantic request/response models
    services/      # Business logic
    integrations/  # External provider wrappers (OAuth, ElevenLabs, Imagen, R2)
    workers/       # Celery task implementations
    tasks/         # Celery app config
  alembic/         # DB migrations
  tests/

frontend/
  src/
    views/         # Page-level Vue components
    components/    # Reusable Vue components
    composables/   # Vue composables (reusable logic)
    stores/        # Pinia state stores
    services/      # API client functions
    router/        # Vue Router config

docs/              # Architecture and design docs
```

## Domain Model

Core backbone: `User -> Child -> Story -> StoryPage`

**Critical concept separations:**
- `users` = app account (owns all product data). `auth_identities` = login methods (one user can have password + Google + Apple).
- `voice_profiles` = usable cloned voice. `voice_samples` = raw uploaded recordings used to train a profile. Never merge these.
- `story_pages` = first-class entities with their own status, image/audio assets, and generation history.
- `assets` table = generic metadata for all files (images, audio, voice samples, covers). File bytes live in object storage only.
- `story_generation_jobs` = explicit async workflow tracking. Do not infer job state from `stories.status` alone.

**Canonical naming** (use consistently across ORM, migrations, schemas, and docs):
`user`, `auth_identity`, `child`, `voice_profile`, `voice_sample`, `story`, `story_page`, `asset`, `story_generation_job`, `story_page_generation`, `subscription`, `plan`, `usage_record`, `consent`, `audit_event`

## Auth Rules

- Users log in via `auth_identities`. Do NOT add `google_sub`, `password_hash`, etc. directly to `users`.
- OAuth identities: store `provider_user_id` (stable subject ID), not just email. `password_hash = NULL`.
- Password identities: `password_hash` using Argon2id. No separate salt column (salt is embedded in the hash).
- Use `(provider, provider_user_id)` as the unique constraint for OAuth identities.
- JWT in HTTP-only secure cookies. Access token: SameSite=Lax, 15min. Refresh token: SameSite=Strict, 7d, path `/api/auth/refresh`.
- Do not silently auto-merge accounts on email match alone — require explicit confirmation.

## Storage Rules

- **Private buckets only.** Signed URLs for all access (upload: ~5min, read: ~5-15min).
- Never store signed URLs in the database — generate them on demand after auth + ownership checks.
- Object key layout: `voice-samples/{user_id}/{voice_profile_id}/{uuid}.wav`, `stories/{user_id}/{story_id}/pages/{page_number}/image/{uuid}.webp`, etc.
- Raw voice samples are the most sensitive asset tier — avoid frontend direct-read access.

## Engineering Rules

- API requests must be fast: validate -> persist -> enqueue -> return. All AI generation is async.
- Every generation step must be retryable at the page level. A failed page should not require full story regeneration.
- Keep provider-specific code behind service interfaces in `app/integrations/`.
- Use explicit status enums and UUID primary keys. Track all timestamps.
- Prefer modular monolith over microservices for v1.

## Out of Scope for v1

Microservice decomposition, collaborative editing, multi-parent family accounts, complex shared story permissions, synchronous in-request media generation.
