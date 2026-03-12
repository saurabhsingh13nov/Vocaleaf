# Vocaleaf

Vocaleaf is a personalized children's storybook app with:

- parent accounts and child profiles
- AI-generated story text
- AI-generated illustrations
- cloned parent voice narration
- private storage for uploaded and generated media

The current product direction is a FastAPI backend plus background workers, PostgreSQL for state, Redis for queue/cache, object storage for media, and a Vue 3 frontend.

## Current Status

This repository is in an early build stage.

- Backend foundation exists: FastAPI app, auth endpoints, SQLAlchemy models, Alembic migration, and backend tests.
- Frontend now has the phase 3 auth flow, protected routing, and frontend unit tests.
- Architecture and schema docs are ahead of feature implementation by design.

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
uv run uvicorn app.main:app --reload
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
npm run test:unit
npm run build
```

## Key Docs

- [Architecture](docs/architecture.md)
- [Schema](docs/schema.md)
- [Auth](docs/auth.md)
- [Storage](docs/storage.md)
- [Voice](docs/voice.md)
- [Story Generation](docs/story-generation.md)
- [Build Plan](docs/plans/2026-03-11-build-plan.md)
- [Claude Code Guidance](CLAUDE.md)

## Core Modeling Rules

- `users` is the app account. `auth_identities` stores login methods.
- `voice_profiles` are usable cloned voices. `voice_samples` are raw uploaded recordings.
- `stories` is the top-level story. `story_pages` stores page-level text and assets.
- `assets` stores metadata only. File bytes belong in object storage.
- Story generation is asynchronous. API requests should persist, enqueue, and return.

## What Exists Today

Backend:

- health endpoint
- email/password auth endpoints
- JWT cookie auth flow
- initial schema models and migration for core domain tables

Frontend:

- Vue auth flow with login, register, logout, and dashboard routing
- frontend unit tests for auth store, router guards, and auth views
- build tooling and lint/type-check setup

## Notes

- Media is intended to be private by default and accessed through signed URLs.
- Voice samples are treated as highly sensitive and should not be exposed publicly.
- If architecture, schema, auth, storage, voice, or generation behavior changes, update the matching doc under `docs/`.
