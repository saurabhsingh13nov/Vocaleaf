# Vocaleaf

Vocaleaf is a personalized children's storybook app with:

- parent accounts and child profiles
- AI-generated story text
- AI-generated illustrations
- cloned parent voice narration
- private storage for uploaded and generated media

The current product direction is a FastAPI backend plus background workers, PostgreSQL for state, Redis for queue/cache, object storage for media, and a Vue 3 frontend.

## Current Status

This repository is in active development — phases 0 through 9 are complete.

- **Phase 0:** Project scaffolding — FastAPI + Vue 3 + Docker Compose
- **Phase 1:** Database models — 17 ORM models, 12 enums, Alembic migrations
- **Phase 2:** Auth backend — Argon2id passwords, JWT cookies, 5 endpoints, 22 tests
- **Phase 3:** Auth frontend — Vue login/register/dashboard, Pinia store, route guards
- **Phase 4:** Child profiles CRUD — full-stack create/read/update/delete with ownership isolation
- **Phase 5:** Google OAuth — Sign in with Google (ID token flow) + account linking flow when email conflicts with an existing password account
- **Phase 6:** Storage & asset service — signed upload/read URLs, upload confirmation, R2 integration boundary, and private asset metadata lifecycle
- **Phase 7:** Voice profiles and sample upload — profile creation with consent capture, browser recording/file upload, signed R2 sample uploads, sample/profile deletion, and private sample metadata lifecycle
- **Phase 8:** Celery + voice cloning worker — Redis-backed job execution, manual clone initiation, official ElevenLabs Python SDK integration boundary, prefork-safe async worker sessions, profile-status polling, and a refreshed mobile-first UI across the current app surfaces
- **Phase 9:** Story creation + text generation — story create/list/detail APIs, Anthropic integration boundary, Celery text worker, generation polling, and story detail UI with page-level text output

Architecture and schema docs are ahead of feature implementation by design.

## Tech Stack

- Backend: FastAPI, SQLAlchemy 2.0 async, Alembic, `uv`
- Frontend: Vue 3, Vite, TypeScript, Pinia, Tailwind CSS
- Database: PostgreSQL 16
- Queue/cache: Redis 7
- Job system direction: Celery
- Object storage direction: Cloudflare R2 or another S3-compatible provider
- Auth: JWT in HTTP-only cookies, Argon2id password hashing
- AI provider direction: Claude for text, Google Imagen for images, ElevenLabs for voice cloning and TTS

## Repository Layout

```text
backend/     FastAPI app, DB models, migrations, backend tests
frontend/    Vue 3 frontend
docs/        Architecture, schema, auth, storage, and feature design docs
```

## Local Development

Start infrastructure from the repository root:

```bash
docker compose up -d
```

Run the backend:

```bash
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --reload-dir app --reload-exclude '.venv/*'
```

Run the frontend in a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Useful checks:

```bash
cd backend
uv run pytest

cd frontend
npm run test:unit -- --run
npm run build
```

Run the Celery worker when voice cloning or later generation tasks are in use:

```bash
cd backend
uv run celery -A app.tasks.celery_app worker --loglevel=info
```

## Key Docs

- [Architecture](docs/architecture.md)
- [Schema](docs/schema.md)
- [Auth](docs/auth.md)
- [Storage](docs/storage.md)
- [Voice](docs/voice.md)
- [Story Generation](docs/story-generation.md)
- [Phase 9 Plan — Story Text Generation](docs/plans/phase-9-story-text-generation.md)
- [Build Plan](docs/plans/2026-03-11-build-plan.md)
- [Claude Code Guidance](CLAUDE.md)

## Core Modeling Rules

- `users` is the app account. `auth_identities` stores login methods.
- `voice_profiles` are usable cloned voices. `voice_samples` are raw uploaded recordings.
- `stories` is the top-level story. `story_pages` stores page-level text and assets.
- `assets` stores metadata only. File bytes belong in object storage.
- Story generation is asynchronous. API requests should persist, enqueue, and return.

## Code Readability

- Prefer readable names and small functions before reaching for comments.
- Add docstrings for non-trivial modules, services, workers, and integration boundaries.
- Add inline comments only when intent is not obvious from the code itself.
- Do not write tutorial comments or narrate simple assignments, branches, or framework basics.
- When touching existing code, improve missing comments only where the added context materially helps.

## What Exists Today

Backend:

- health endpoint
- email/password auth endpoints (register, login, logout, refresh, me)
- JWT cookie auth flow (access 15min + refresh 7d)
- Google OAuth — Sign in with Google via ID token; account linking (`POST /api/auth/link-google`) when the email already has a password account
- child profiles CRUD with per-user ownership enforcement
- asset upload URL, confirm, and signed read endpoints with ownership enforcement
- voice profile creation/listing/detail plus voice sample upload/confirm/delete, manual clone initiation, and profile delete endpoints
- Celery-backed voice clone worker that downloads uploaded samples from R2, calls the official ElevenLabs Python SDK, stores provider voice IDs on success, and uses process-local async DB sessions under the normal Celery prefork pool
- story creation/list/detail endpoints with owned child/voice validation and latest generation error surfacing
- Celery-backed text generation worker that calls Anthropic, validates structured page output, stores `story_pages` and `story_page_generations`, and marks text-complete stories as ready for phase 9
- 17 ORM models and Alembic migrations for the full domain schema
- 94 backend tests

Frontend:

- Vue auth flow with login, register, logout, and dashboard routing
- Google Sign-In button on login and register pages; link-mode form when a 409 conflict occurs
- child profiles management page with create/edit/delete
- voice profiles page with consent-gated profile creation, in-browser recording, file upload, sample deletion, profile deletion, manual clone trigger, and automatic status polling
- story creation form, story detail view, generation polling, and dashboard recent-stories surface
- clearer phase-7 profile status labels in the UI (`Add samples`, `Awaiting clone`) instead of the raw backend `pending` state
- mobile-first warm editorial refresh across the current auth, dashboard, children, and voice surfaces
- Pinia stores for auth, children, voice, and story state
- 58 frontend unit tests for stores, router guards, auth views (including link-mode), children views, voice flows, and story flows
- build tooling and lint/type-check setup

Not yet built:

- image generation workflows (Phase 10)
- audio/TTS narration workflows (Phase 11)
- story reader/playback UI (Phase 12)
- provider-side voice deletion and preview sample generation

## Notes

- Media is intended to be private by default and accessed through signed URLs.
- Voice samples are treated as highly sensitive and should not be exposed publicly.
- The current frontend direction is mobile-first and intentionally restrained rather than heavily decorative.
- If architecture, schema, auth, storage, voice, or generation behavior changes, update the matching doc under `docs/`.
