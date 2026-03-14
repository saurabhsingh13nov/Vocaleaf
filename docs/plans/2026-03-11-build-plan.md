# Vocaleaf — Full Project Build Plan

## Context

Vocaleaf is a personalized children's storybook web app. This plan started before implementation and now serves mostly as a historical roadmap plus a record of the chosen implementation direction.

## Current Repo Status (March 14, 2026)

- Phase 0 complete: backend/frontend scaffolding, local tooling, and Docker Compose exist.
- Phase 1 complete: core SQLAlchemy models and the initial Alembic migration exist.
- Phase 2 complete: email/password auth and JWT cookie auth exist in the FastAPI backend.
- Phase 3 complete: Vue auth flow, protected routing, and frontend unit tests exist.
- Phase 4 complete: child profiles CRUD — backend (schemas, service, routes, 17 tests) and frontend (service, Pinia store, components, view, 4 tests).
- Phase 5 complete: Google OAuth — Sign in with Google (ID token flow) + account linking flow; auth and frontend coverage remain in place under the current test suite.
- Phase 6 complete: storage and asset service — R2 integration boundary, signed upload/read URLs, upload confirmation, explicit asset upload lifecycle, backend asset tests, and manual local verification against a real R2 bucket.
- Phase 7 complete: voice profiles and sample upload — consent-gated profile creation, voice profile listing, direct signed voice-sample uploads, sample confirmation, sample/profile deletion with raw-storage cleanup, browser recording/file-upload UI, clearer phase-7 status labels, and frontend/backend test coverage.
- Phase 8 complete: Celery + voice cloning worker — Redis-backed Celery app, manual clone initiation, official ElevenLabs Python SDK integration boundary, prefork-safe async worker sessions, profile detail polling, worker-driven status transitions, and a mobile-first UI refresh across the current product surfaces.
- Phase 9 complete: story creation + text generation — Anthropic integration boundary, story create/list/detail APIs, Celery text worker, dashboard recent-story surface, story creation form, and story detail polling with page-level text output.
- Phase 10 complete: story illustration generation — Gemini image generation, private page-image assets, signed illustration playback, and completion tracking after illustrations finish.
- Phase 11 complete: per-page narration audio — ElevenLabs TTS generation, private page-audio assets, signed narration playback, and narration-aware completion tracking.
- Phase 12 complete: reader/playback UI — all-pages gallery, focused book view, inline full-text expansion, line-by-line narration reveal, and narration-driven autoplay with a one-second gap between pages.
- `npm run build` and all tests pass.

## Tech Stack (Locked In)

| Layer | Choice |
|---|---|
| Backend | FastAPI (Python 3.12+) |
| Frontend | Vue 3 (Composition API) + Vite + Tailwind CSS |
| State management | Pinia |
| Database | PostgreSQL 16 |
| ORM / Migrations | SQLAlchemy 2.0 (async) + Alembic |
| Queue | Celery + Redis |
| Auth | JWT in HTTP-only cookies (access + refresh tokens) |
| Object storage | Cloudflare R2 (S3-compatible, via boto3) |
| Text AI | Claude (Anthropic API) |
| Image AI | Google Imagen (via google-generativeai SDK) |
| Voice AI | ElevenLabs (voice cloning + TTS) |
| Python deps | uv |
| Local infra | Docker Compose (Postgres + Redis only) |

## Project Structure

```
vocaleaf/
├── backend/
│   ├── app/
│   │   ├── api/              # FastAPI route handlers
│   │   │   ├── auth.py
│   │   │   ├── children.py
│   │   │   ├── stories.py
│   │   │   ├── voice.py
│   │   │   ├── assets.py
│   │   │   └── health.py
│   │   ├── core/             # Config, settings, constants
│   │   │   ├── config.py
│   │   │   └── security.py
│   │   ├── db/               # Database session + base
│   │   │   ├── session.py
│   │   │   └── base.py
│   │   ├── models/           # SQLAlchemy ORM models
│   │   │   ├── user.py
│   │   │   ├── auth_identity.py
│   │   │   ├── child.py
│   │   │   ├── voice_profile.py
│   │   │   ├── voice_sample.py
│   │   │   ├── story.py
│   │   │   ├── story_page.py
│   │   │   ├── asset.py
│   │   │   ├── story_generation_job.py
│   │   │   └── ...
│   │   ├── schemas/          # Pydantic request/response models
│   │   ├── services/         # Business logic
│   │   │   ├── auth.py
│   │   │   ├── story.py
│   │   │   ├── voice.py
│   │   │   └── asset.py
│   │   ├── integrations/     # External provider wrappers
│   │   │   ├── anthropic.py    # Claude for text
│   │   │   ├── google_imagen.py # Imagen for images
│   │   │   ├── elevenlabs.py   # Voice cloning + TTS
│   │   │   ├── google_oauth.py
│   │   │   └── r2.py           # Cloudflare R2
│   │   ├── workers/          # Celery task implementations
│   │   │   ├── text_worker.py
│   │   │   ├── image_worker.py
│   │   │   ├── audio_worker.py
│   │   │   └── voice_clone_worker.py
│   │   ├── tasks/            # Celery task definitions
│   │   │   └── celery_app.py
│   │   └── main.py           # FastAPI app entry point
│   ├── alembic/
│   ├── tests/
│   ├── pyproject.toml
│   └── alembic.ini
├── frontend/
│   ├── src/
│   │   ├── components/       # Reusable Vue components
│   │   ├── views/            # Page-level Vue components
│   │   ├── composables/      # Vue composables (reusable logic)
│   │   ├── stores/           # Pinia stores
│   │   ├── router/           # Vue Router config
│   │   ├── services/         # API client functions
│   │   ├── assets/           # Static assets
│   │   ├── App.vue
│   │   └── main.ts
│   ├── index.html
│   ├── tailwind.config.js
│   ├── vite.config.ts
│   ├── tsconfig.json
│   └── package.json
├── docker-compose.yml        # Postgres + Redis
├── docs/                     # Existing architecture docs
└── CLAUDE.md
```

---

## Build Phases

### Phase 0: Project Scaffolding
**Goal:** Working dev environment with "Hello World" on both ends.

**Backend:**
- `uv init` the backend project
- Install core deps: `fastapi`, `uvicorn`, `sqlalchemy[asyncio]`, `asyncpg`, `alembic`, `pydantic-settings`
- Create `app/main.py` with a health check endpoint
- Create `docker-compose.yml` with Postgres 16 + Redis 7
- Configure `app/core/config.py` with pydantic-settings (DATABASE_URL, REDIS_URL, secrets)
- Set up async SQLAlchemy session factory in `app/db/session.py`
- Initialize Alembic with async support

**Frontend:**
- `npm create vue@latest` with TypeScript + Vue Router + Pinia
- Add Tailwind CSS via `@tailwindcss/vite`
- Create a landing page that calls the backend health endpoint
- Configure Vite proxy to forward `/api` to FastAPI (avoids CORS in dev)

**Vue.js learning moment:** _Vue 3 Composition API basics — `<script setup>`, `ref()`, `onMounted()`, template syntax. How Vite hot-reloads. How the Vue project is structured (views vs components)._

**Verification:** `docker compose up -d` starts Postgres + Redis. `uv run uvicorn app.main:app` serves the API. `npm run dev` shows the Vue app calling the health endpoint.

---

### Phase 1: Database Models & Migrations
**Goal:** All core tables from `docs/schema.md` exist in Postgres.

**Create SQLAlchemy models for:**
- `users`, `auth_identities` (identity & auth group)
- `children` (family profiles group)
- `voice_profiles`, `voice_samples` (voice system group)
- `stories`, `story_pages` (story system group)
- `assets` (file/assets group)
- `story_generation_jobs`, `story_page_generations` (operations group)
- `plans`, `subscriptions` (billing group)
- `consents`, `audit_events`, `usage_records` (compliance group)

**Key patterns:**
- UUID primary keys via `uuid7` or `uuid.uuid4`
- Enum types for status fields (e.g., `UserStatus`, `StoryStatus`, `JobStatus`)
- `created_at` / `updated_at` timestamps on all tables
- Unique constraints per `docs/schema.md`: `(provider, provider_user_id)`, `(story_id, page_number)`, etc.

**Generate initial Alembic migration and apply.**

**Verification:** `alembic upgrade head` creates all tables. Inspect with `psql` or a DB tool.

---

### Phase 2: Auth — Backend
**Goal:** Email/password signup + login + JWT cookie auth working via API.

**Build:**
- `app/core/security.py` — Argon2id password hashing (via `argon2-cffi`), JWT creation/verification (via `python-jose`), cookie helpers
- `app/services/auth.py` — signup, login, token refresh logic
- `app/api/auth.py` — endpoints:
  - `POST /api/auth/register` — create user + password auth_identity
  - `POST /api/auth/login` — verify password, set JWT cookies
  - `POST /api/auth/logout` — clear cookies
  - `POST /api/auth/refresh` — rotate access token
  - `GET /api/auth/me` — return current user from JWT
- `app/api/dependencies.py` — `get_current_user` dependency that extracts JWT from cookies

**JWT cookie design:**
- Access token: HTTP-only, Secure, SameSite=Lax, short expiry (15 min)
- Refresh token: HTTP-only, Secure, SameSite=Strict, longer expiry (7 days), path restricted to `/api/auth/refresh`

**Verification:** Use `curl` or httpie to register, login (check Set-Cookie headers), call `/me`, refresh, logout.

---

### Phase 3: Auth — Frontend
**Goal:** Signup, login, logout, and protected routes working in Vue.

**Build:**
- `src/services/api.ts` — Axios instance configured with `withCredentials: true` (sends cookies)
- `src/stores/auth.ts` — Pinia store: `user` state, `login()`, `register()`, `logout()`, `fetchUser()` actions
- `src/views/LoginView.vue` — login form
- `src/views/RegisterView.vue` — registration form
- `src/views/DashboardView.vue` — protected landing page after login
- `src/router/index.ts` — route guards using `beforeEach` to redirect unauthenticated users
- `src/composables/useAuth.ts` — composable wrapping the auth store for easy use in components

**Vue.js learning moment:** _Pinia stores (reactive state management), Vue Router navigation guards, `v-model` for two-way form binding, `async/await` in Vue composables, conditional rendering with `v-if`._

**Verification:** Register a user, login, see dashboard, refresh page (stays logged in via cookie), logout, get redirected to login.

---

### Phase 4: Child Profiles (Full CRUD)
**Goal:** First real feature — create/read/update/delete child profiles.

**Backend:**
- `app/schemas/child.py` — Pydantic models for create/update/response
- `app/services/child.py` — CRUD operations scoped to current user
- `app/api/children.py` — endpoints:
  - `GET /api/children` — list user's children
  - `POST /api/children` — create child profile
  - `GET /api/children/{id}` — get one
  - `PUT /api/children/{id}` — update
  - `DELETE /api/children/{id}` — delete (soft or hard)

**Frontend:**
- `src/views/ChildrenView.vue` — list children, add button
- `src/components/ChildForm.vue` — reusable form for create/edit
- `src/components/ChildCard.vue` — display card for each child
- `src/stores/children.ts` — Pinia store for child data

**Vue.js learning moment:** _Component props and events (`defineProps`, `defineEmits`), `v-for` list rendering, component composition, reactive forms, Tailwind utility classes for layout._

**Verification:** Create, edit, and delete child profiles through the UI. Refresh page — data persists.

---

### Phase 5: Google OAuth ✅
**Goal:** "Sign in with Google" button that creates/links accounts.

**Backend:**
- `app/integrations/google_oauth.py` — verify Google ID token via `google-auth`, return `GoogleUserInfo`
- `app/services/auth.py` — `authenticate_google_user()`: find by `(GOOGLE, sub)` or create; 409 on email conflict with password account
- `app/services/auth.py` — `link_google_identity()`: verify password ownership, then attach a Google `AuthIdentity` to an existing user (idempotent)
- `app/api/auth.py` — `POST /api/auth/google` endpoint; `POST /api/auth/link-google` endpoint for the conflict linking flow
- 8 backend tests covering: new user, returning user, invalid token, email conflict, provider_user_id validation, link success, wrong password, idempotent link

**Frontend:**
- Google Identity Services JS SDK loaded dynamically in `onMounted`
- Google Sign-In button on both LoginView and RegisterView with "or" divider
- `loginWithGoogle()` and `linkWithGoogle()` store actions; `googleAuth()` and `linkGoogleAccount()` service functions
- 409 conflict triggers link-mode form (password prompt + Link/Cancel) instead of a dead-end error message; satisfies the auth.md rule against silent auto-merge
- 8 frontend tests covering link-mode for both views: 409 → link form, correct password → dashboard, wrong password → error, Cancel → normal form

**Verification:** Phase 5 shipped with passing backend/frontend tests and a clean frontend build; the current suite has grown further in later phases.

---

### Phase 6: Storage & Asset Service ✅
**Goal:** Upload and retrieve files from Cloudflare R2 via signed URLs.

**Backend:**
- `app/integrations/r2.py` — boto3 client configured for R2 endpoint, generate signed upload/download URLs
- `app/services/asset.py` — create asset metadata, issue signed URLs with ownership checks
- `app/api/assets.py` — endpoints:
  - `POST /api/assets/upload-url` — returns signed upload URL + asset_id
  - `POST /api/assets/{id}/confirm` — mark upload complete
  - `GET /api/assets/{id}/url` — returns signed read URL (auth + ownership checked)

**Set up R2:**
- Create a Cloudflare R2 bucket (private)
- Generate R2 API tokens (Access Key ID + Secret)
- Add to config/env vars

**Verification:** Request upload URL, upload a test file with `curl`, confirm it, request read URL, download file.

---

### Phase 7: Voice Sample Upload & Profile Creation ✅
**Goal:** Upload voice samples and create voice profiles (no cloning yet).

**Backend:**
- `app/schemas/voice.py` — voice_profile and voice_sample Pydantic models
- `app/services/voice.py` — create profiles, handle sample uploads, track lifecycle
- `app/api/voice.py` — endpoints:
  - `POST /api/voice-profiles` — create a voice profile
  - `GET /api/voice-profiles` — list user's profiles
  - `POST /api/voice-profiles/{id}/samples` — initiate voice sample upload (returns signed URL)
  - `POST /api/voice-profiles/{id}/samples/{sample_id}/confirm` — confirm upload complete

**Frontend:**
- `src/views/VoiceProfilesView.vue` — list profiles, create new
- `src/components/VoiceRecorder.vue` — record audio in-browser using MediaRecorder API or file upload
- `src/components/VoiceSampleList.vue` — show uploaded samples per profile

**Vue.js learning moment:** _Working with browser APIs (MediaRecorder) in Vue, file upload patterns, progress tracking with reactive state, direct-to-storage uploads._

**Verification:** Create a voice profile, upload a voice sample, see it listed, delete stale/pending samples, delete an accidental profile, and confirm the corresponding raw object cleanup in R2.

---

### Phase 8: Celery + Voice Cloning Worker ✅
**Goal:** Background job infrastructure + first real worker (voice cloning via ElevenLabs).

**Backend:**
- `app/tasks/celery_app.py` — Celery app configured with Redis broker
- `app/workers/voice_clone_worker.py` — task that:
  1. Downloads voice samples from R2
  2. Calls ElevenLabs voice cloning API
  3. Updates `voice_profiles` with `provider_voice_id` and status = ready/failed
- `app/integrations/elevenlabs.py` — ElevenLabs API wrapper (clone voice, list voices)
- Add `POST /api/voice-profiles/{id}/clone` endpoint — enqueues clone task, returns job status
- Add status polling endpoint: `GET /api/voice-profiles/{id}` returns current status

**Frontend:**
- Add "Clone Voice" button to voice profile view
- Poll for status updates (or use simple polling composable)

**Shipped shape:** Clone initiation is manual, profile status remains the only user-facing async state, the worker uses process-local async DB sessions under Celery prefork, and the current app surfaces were refreshed into a calmer mobile-first UI during this phase.

**Verification:** Upload samples, trigger clone, watch status go from `processing` to `ready`. Check ElevenLabs dashboard to confirm voice exists.

---

### Phase 9: Story Creation & Text Generation
**Detailed plan:** [`docs/plans/phase-9-story-text-generation.md`](phase-9-story-text-generation.md)

**Goal:** Create a story and generate text content (title, page plan, narration text per page).

**Backend:**
- `app/schemas/story.py` — story create/response models
- `app/services/story.py` — create story, create generation job, fetch stories
- `app/api/stories.py` — endpoints:
  - `POST /api/stories` — create story + enqueue generation
  - `GET /api/stories` — list user's stories
  - `GET /api/stories/{id}` — get story with pages and status
- `app/workers/text_worker.py` — Celery task that:
  1. Calls Claude API with child profile context + story prompt
  2. Gets structured JSON output: title, page outlines, narration text, image prompts per page
  3. Creates `story_pages` rows with text content + image prompts
  4. Updates story status
  5. Dispatches image + audio tasks
- `app/integrations/anthropic.py` — Claude API wrapper with structured output prompting

**Frontend:**
- `src/views/StoryCreateView.vue` — story creation form (select child, enter prompt, pick theme/art style)
- `src/views/StoryDetailView.vue` — show story with generation status, text content as it becomes available
- `src/stores/stories.ts` — Pinia store

**Vue.js learning moment:** _Multi-step forms, select dropdowns with `v-model`, watching reactive data changes, dynamic component rendering based on status._

**Verification:** Create a story for a child profile, watch text generation complete, see page text on the story detail page.

---

### Phase 10: Image Generation
**Goal:** Generate illustrations for each story page using Google Imagen.

**Backend:**
- `app/workers/image_worker.py` — Celery task that:
  1. Takes page image prompt + art style + continuity notes
  2. Calls Google Imagen API
  3. Uploads generated image to R2
  4. Creates asset row
  5. Links asset to `story_pages.image_asset_id`
  6. Updates page status
- `app/integrations/google_imagen.py` — Imagen API wrapper

**Frontend:**
- Update `StoryDetailView.vue` to display page images (loaded via signed URLs)
- Image loading states (skeleton/placeholder while generating)

**Verification:** After text generation, images should auto-generate. Story detail shows illustrations for each page.

**Bugfix (2026-03-13):** SDK TypeError (`GenerateImageConfig` → `GenerateImagesConfig`) + enum fields needed actual enum instances. Also fixed infinite frontend polling when image generation fails by propagating FAILED status to story and job.

**Follow-up — Delete story feature:** Allows deleting stories in any status (READY, GENERATING, FAILED) via three-dot menu + confirmation modal. See [`docs/plans/2026-03-13-delete-story-feature.md`](./2026-03-13-delete-story-feature.md) for full plan. Partially implemented — backend done, frontend modal WIP.

---

### Phase 11: Audio Narration
**Goal:** Generate per-page narration audio using ElevenLabs TTS with cloned voice.

**Backend:**
- `app/workers/audio_worker.py` — Celery task that:
  1. Takes page text + voice profile's `provider_voice_id`
  2. Calls ElevenLabs TTS API
  3. Uploads audio to R2
  4. Creates asset row
  5. Links to `story_pages.audio_asset_id`
  6. Records duration
  7. Updates page status
- Extend `app/integrations/elevenlabs.py` with TTS function

**Frontend:**
- Audio player component per page
- Overall story status reflects all pages complete

**Verification:** Story with cloned voice profile generates narrated audio per page. Play audio in browser.

---

### Phase 12: Story Reader / Playback ✅
**Goal:** Full story reading experience — page-by-page with illustrations and synced audio.

**Frontend:**
- focused reader behavior delivered inside the story detail route rather than a separate reader route
- all-pages gallery, focused book view, and narration-driven autoplay mode
- large illustration-first layout with inline narration-line reveal and expandable full text
- shared playback composable for page transitions, autoplay timing, and active-line state

**Vue.js learning moment:** _Advanced component composition, `<Transition>` for page animations, audio element control with refs, keyboard navigation events, responsive design with Tailwind._

**Verification:** Open a completed narrated story in story detail. Switch between all-pages, book view, and autoplay; hear narration, see illustrations, and watch the reader advance after each page finishes.

---

### Phase 13: Consent & Audit (Required for Voice Features)
**Goal:** Record explicit consent for voice cloning, track key actions.

**Backend:**
- `app/api/consent.py` — `POST /api/consents` to record consent
- `app/services/audit.py` — helper to log audit events
- Gate voice cloning behind consent check
- Log: account creation, voice clone requests, story generation, data deletion

**Frontend:**
- Consent modal before first voice clone
- Consent status indicator on voice profile page

**Verification:** Cannot clone voice without accepting consent. Audit events appear in DB for key actions.

---

### Phase 14: Subscriptions & Usage Tracking
**Goal:** Plan-based feature gating and usage metering.

**Backend:**
- Seed `plans` table with free + paid tiers
- `app/services/subscription.py` — check active plan, enforce limits
- `app/services/usage.py` — record usage (stories created, images generated, TTS chars)
- Apply limits at story creation and generation endpoints
- (Stripe integration deferred — start with manual plan assignment)

**Frontend:**
- `src/views/SubscriptionView.vue` — show current plan, usage stats
- Limit feedback in UI when quota reached

**Verification:** Free plan user hits story limit, gets blocked with clear message. Usage records appear in DB.

---

## Cross-Cutting Concerns (Build Alongside Phases)

**Error handling:** FastAPI exception handlers returning consistent JSON errors. Vue global error interceptor in Axios.

**Testing strategy:**
- Backend: pytest + httpx (async test client) for API tests, unit tests for services
- Frontend: Vitest for unit tests, Playwright for key E2E flows (login, create story)
- Run tests: `uv run pytest` (backend), `npm run test` (frontend)

**Observability:** Structured logging with `structlog`. Request ID middleware. Celery task logging.

**Email verification & password reset:** Can be added after Phase 5 as a refinement. Use a transactional email provider (Resend, SendGrid).

---

## Dev Commands Reference

```bash
# Infrastructure
docker compose up -d                    # Start Postgres + Redis
docker compose down                     # Stop infra

# Backend
cd backend
uv sync                                 # Install deps
uv run alembic upgrade head             # Run migrations
uv run uvicorn app.main:app --reload    # Start API server
uv run celery -A app.tasks.celery_app worker --loglevel=info  # Start worker
uv run pytest                           # Run tests
uv run pytest tests/test_auth.py -k "test_login"  # Single test

# Frontend
cd frontend
npm install                             # Install deps
npm run dev                             # Start dev server (Vite)
npm run build                           # Production build
npm run test                            # Run Vitest
npm run lint                            # Lint
```

## Verification Strategy

After each phase, verify by:
1. Running the relevant backend tests
2. Testing the feature through the Vue UI manually
3. Checking data in Postgres (via psql or a DB client)
4. For storage phases: confirming objects exist in R2
5. For worker phases: checking Celery logs + job status in DB
