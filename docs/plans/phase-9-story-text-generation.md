# Phase 9: Story Creation & Text Generation — Implementation Plan

## Context

Phases 0-8 are complete (auth, child profiles, Google OAuth, R2 storage, voice profiles, voice cloning). Phase 9 is the core product feature: users create a personalized story for their child, and Claude generates structured text content (title, narration text per page, image prompts, continuity notes) asynchronously via a Celery worker. This phase builds the foundation that Phases 10-12 (images, audio, reader UI) plug into.

## Scope

- Backend: Anthropic integration, story schemas, story service, story API, text worker
- Frontend: stories API client, Pinia store with polling, StoryCreateView, StoryDetailView
- Tests: backend API + worker tests, frontend store tests
- **Out of scope:** Image generation, audio/TTS, story reader/playback UI (Phases 10-12)

## Files to Create (10 new)

| # | File | Purpose |
|---|------|---------|
| 1 | `backend/app/integrations/anthropic.py` | Claude API wrapper |
| 2 | `backend/app/schemas/story.py` | Pydantic request/response models |
| 3 | `backend/app/services/story.py` | Story creation + retrieval logic |
| 4 | `backend/app/api/stories.py` | FastAPI route handlers |
| 5 | `backend/app/workers/text_worker.py` | Celery text generation task |
| 6 | `backend/tests/test_stories.py` | Backend tests |
| 7 | `frontend/src/services/stories.ts` | API client functions |
| 8 | `frontend/src/stores/stories.ts` | Pinia store with generation polling |
| 9 | `frontend/src/views/StoryCreateView.vue` | Story creation form |
| 10 | `frontend/src/views/StoryDetailView.vue` | Story detail + generation status |

## Files to Modify (7 existing)

| File | Change |
|------|--------|
| `backend/pyproject.toml` | Add `anthropic` SDK dependency |
| `backend/app/core/config.py` | Add `anthropic_api_key`, `anthropic_model` settings |
| `backend/app/tasks/celery_app.py` | Register text_worker import |
| `backend/app/main.py` | Register stories router |
| `frontend/src/router/index.ts` | Add `/stories/new` and `/stories/:id` routes |
| `frontend/src/views/DashboardView.vue` | Add "Create Story" tile + recent stories |
| `frontend/src/assets/main.css` | Add theme-pill, generating animation styles |

## Existing Patterns to Reuse

- **Worker pattern:** `backend/app/workers/voice_clone_worker.py` — sync Celery task wrapping async logic via `asyncio.run()`, session_factory, failure cleanup
- **Service pattern:** `backend/app/services/voice.py` — custom `XError(message, status_code)`, ownership checks, async functions
- **API pattern:** `backend/app/api/voice.py` — FastAPI router, `get_current_user` dependency, HTTPException conversion
- **Integration pattern:** `backend/app/integrations/elevenlabs.py` — thin client class, custom exception, module-level factory
- **Store polling pattern:** `frontend/src/stores/voice.ts` — `generatingIds` + `setTimeout` polling loop
- **Design system:** `frontend/src/assets/main.css` — `surface-card`, `page-kicker`, `page-title`, `primary-button`, `field-input`, `status-pill`

---

## Implementation Steps

### Step 1: Backend config + dependency

Add `"anthropic>=0.52.0"` to `backend/pyproject.toml` dependencies.

Add to `Settings` in `backend/app/core/config.py`:
```python
# Anthropic (Claude)
anthropic_api_key: str = ""
anthropic_model: str = "claude-sonnet-4-20250514"
```

Run `uv sync` to install.

### Step 2: Anthropic integration (`backend/app/integrations/anthropic.py`)

Thin wrapper around the `anthropic` Python SDK.

**Dataclasses:**
- `StoryPageOutput(page_number, text_content, image_prompt, continuity_notes)`
- `StoryTextOutput(title, pages: list[StoryPageOutput])`

**`AnthropicClient` class:**
- `__init__(api_key, model)`
- `generate_story_text(child_name, child_age, favorite_themes, favorite_characters, prompt, theme, art_style, page_count, reading_level, language)` → `StoryTextOutput`

**Prompt design:**
- System: "You are a warm children's storyteller creating personalized bedtime stories..."
- User prompt includes:
  - Child context (name, age, interests/favorites)
  - Story request (user prompt and/or theme)
  - Requirements (page count, reading level, language, art style)
  - Strict JSON schema for the output
- Each page output: `text_content` (2-4 sentences for reading aloud), `image_prompt` (detailed illustration description referencing art style and character appearances), `continuity_notes` (track character appearances, settings for cross-page consistency)
- Parse response with `json.loads()`, strip markdown fences if present
- Raise `AnthropicError` on API or parse failures

**`get_anthropic_client()` factory** (module-level, matches `get_elevenlabs_client()` pattern).

### Step 3: Story schemas (`backend/app/schemas/story.py`)

```python
class StoryCreate(BaseModel):
    child_id: uuid.UUID
    voice_profile_id: Optional[uuid.UUID] = None
    prompt: Optional[str] = Field(default=None, max_length=2000)
    theme: Optional[str] = Field(default=None, max_length=100)
    target_page_count: int = Field(default=6, ge=4, le=12)
    reading_level: Optional[str] = Field(default=None, max_length=50)
    art_style: Optional[str] = Field(default=None, max_length=100)
    language: str = Field(default="en", max_length=10)

class StoryPageResponse(BaseModel):  # from_attributes=True
    id, page_number, text_content, image_prompt, status,
    image_asset_id, audio_asset_id, duration_ms, created_at, updated_at

class StoryResponse(BaseModel):  # from_attributes=True, includes pages sorted by page_number
    id, user_id, child_id, voice_profile_id, title, prompt, theme, status,
    target_page_count, reading_level, language, art_style, created_at, updated_at,
    pages: list[StoryPageResponse]

class StoryListItem(BaseModel):  # lighter response, no pages
    id, child_id, title, theme, status, target_page_count, art_style, created_at, updated_at
```

### Step 4: Story service (`backend/app/services/story.py`)

**`StoryError(message, status_code)`** — custom exception (matches VoiceError pattern).

**`create_story(db, user_id, data)`:**
1. Verify child belongs to user (404 if not)
2. If voice_profile_id given, verify it belongs to user and status=READY (400 if not)
3. Require at least one of `prompt` or `theme` (400 if neither)
4. Create `Story` row (status=DRAFT)
5. Create `StoryGenerationJob` row (job_type="full_generation", status=PENDING, provider_text="anthropic")
6. Commit
7. Enqueue `generate_story_text_task.delay(str(story.id), str(job.id))`
8. Update story status → GENERATING, commit
9. Return story with pages loaded

**`list_stories(db, user_id, limit, offset)`** — user's stories, ordered by created_at DESC, no eager page loading.

**`get_story(db, user_id, story_id)`** — with `selectinload(Story.pages)`, ownership check, returns None if not found/owned.

### Step 5: Story API routes (`backend/app/api/stories.py`)

| Method | Path | Response | Notes |
|--------|------|----------|-------|
| POST | `/api/stories` | 202 + StoryResponse | Create + enqueue |
| GET | `/api/stories` | list[StoryListItem] | Query: limit, offset |
| GET | `/api/stories/{id}` | StoryResponse | 404 if not found/owned |

Register router in `backend/app/main.py`.

### Step 6: Text generation worker (`backend/app/workers/text_worker.py`)

**`generate_story_text_task(story_id, job_id)`** — sync Celery task wrapping async `run_text_generation()` via `asyncio.run()`.

**`run_text_generation(story_id, job_id)`** async core:
1. Load story with child relationship + load job from DB
2. Guard: return early if story/job missing
3. Set job status=RUNNING, started_at=now, story status=GENERATING, commit
4. Build context from child profile (name, age, favorite_themes, favorite_characters)
5. Call `get_anthropic_client().generate_story_text(...)`
6. For each page in response:
   - Create `StoryPage` (page_number, text_content, image_prompt, continuity_notes, status=TEXT_READY)
   - Create `StoryPageGeneration` (generation_type=TEXT, provider="anthropic", request/response payloads stored)
7. Set story title from Claude's response
8. Set job status=COMPLETED, completed_at=now
9. Commit all changes

**Error handling:** On failure → rollback → reload story and job → set story=FAILED, job=FAILED with error_message → commit → log. Celery wrapper catches exceptions, runs failure cleanup, re-raises.

**`mark_text_generation_failed(story_id, job_id)`** — standalone failure cleanup function (matches `mark_voice_clone_failed` pattern).

Register worker import in `backend/app/tasks/celery_app.py`.

### Step 7: Backend tests (`backend/tests/test_stories.py`)

**API tests (~12):**
- Create story success (202, correct fields returned)
- Create with missing / other user's child (404)
- Create with invalid voice profile (400)
- Create with no prompt or theme (400)
- List stories: empty, with data, user isolation
- Get story detail: success, not found, other user's story

**Worker tests (~3, mock AnthropicClient):**
- Successful text generation → pages created with correct text, statuses correct
- AnthropicError → story and job marked FAILED
- Missing story → graceful return

Mock pattern: `FakeAnthropicClient` returning canned `StoryTextOutput`, monkeypatch `get_anthropic_client`. Monkeypatch Celery task to no-op for API tests (so enqueue doesn't run).

### Step 8: Frontend API service (`frontend/src/services/stories.ts`)

TypeScript types: `Story`, `StoryPage`, `StoryListItem`, `CreateStoryPayload`, `StoryStatus`, `StoryPageStatus`

Functions: `createStory()`, `getStories()`, `getStory()` — matching backend endpoints via the shared axios instance.

### Step 9: Frontend Pinia store (`frontend/src/stores/stories.ts`)

**State:** `stories`, `currentStory`, `isLoading`, `error`, `generatingStoryIds`, `pollingTimers`

**Actions:**
- `fetchStories()` — load list
- `createStory(payload)` — call API, add to list, start polling if status=generating
- `fetchStory(storyId)` — load detail with pages
- `scheduleGenerationPoll(storyId)` — poll every 4s while status=generating (same pattern as `scheduleClonePoll` in voice store)
- `stopGenerationPolling(storyId)` / `stopAllPolling()`

When polling resolves (status changes from generating), update both `currentStory` (if matches) and the corresponding entry in the `stories` list.

### Step 10: StoryCreateView (`frontend/src/views/StoryCreateView.vue`)

Warm, inviting creation form. Not a database form — feels like starting a creative journey.

**Sections:**
1. **Header** — page-kicker "Create", page-title "New Story", page-subtitle ("Choose a child, describe your story idea, and let the magic begin.")
2. **Child selector** — dropdown from children store
3. **Story prompt** — textarea ("A brave adventure in the deep ocean with a friendly octopus...")
4. **Theme** — toggleable pill buttons: Adventure, Bedtime, Friendship, Animals, Space, Fantasy, Nature, Ocean
5. **Art style** — toggleable pill buttons: Watercolor, Storybook Classic, Modern Illustration, Whimsical, Dreamy
6. **Page count** — 4 / 6 / 8 pill selector
7. **Voice profile** — optional dropdown (only shown if user has ready voice profiles)
8. **Submit** — primary-button "Create Story", on success redirects to StoryDetailView

**New CSS classes** in main.css:
```css
.theme-pill {
  display: inline-flex; align-items: center;
  border-radius: 999px; padding: 0.5rem 1rem;
  font-size: 0.85rem; font-weight: 600;
  border: 1px solid var(--app-border);
  background: var(--app-surface-strong); color: var(--app-muted);
  cursor: pointer; transition: all 160ms ease;
}
.theme-pill:hover { border-color: var(--app-accent); color: var(--app-ink); }
.theme-pill-active {
  background: var(--app-accent-soft);
  border-color: var(--app-accent);
  color: var(--app-accent-strong);
}
```

### Step 11: StoryDetailView (`frontend/src/views/StoryDetailView.vue`)

Shows story metadata + generation progress + page content as it appears.

**UI states:**
- **Generating:** Gentle dot-pulse animation + "Writing your story..." message + skeleton page card placeholders (animate-pulse)
- **Ready:** Story title (page-title) + metadata card (status/theme/art-style pills, page count, created date) + page cards showing narration text
- **Failed:** Error banner with retry guidance

**Page cards** display:
- Page kicker ("Page 1"), status pill
- Narration text in serif font (Iowan Old Style) for storybook feel
- 4:3 aspect ratio placeholder for future illustration ("Illustration will appear here")
- Placeholder for future audio narration

**Polling:** Starts on mount if status=generating, stops on unmount or when status changes.

**New CSS** in main.css:
```css
.generating-animation { display: flex; justify-content: center; gap: 0.4rem; }
.generating-animation .dot {
  width: 0.5rem; height: 0.5rem; border-radius: 50%;
  background: var(--app-accent);
  animation: dot-pulse 1.4s infinite ease-in-out both;
}
.generating-animation .dot:nth-child(1) { animation-delay: -0.32s; }
.generating-animation .dot:nth-child(2) { animation-delay: -0.16s; }
@keyframes dot-pulse {
  0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
  40% { transform: scale(1); opacity: 1; }
}
```

### Step 12: Router + Dashboard updates

**Router** (`frontend/src/router/index.ts`):
- `/stories/new` → StoryCreateView (requiresAuth)
- `/stories/:id` → StoryDetailView (requiresAuth)

**Dashboard** (`frontend/src/views/DashboardView.vue`):
- Replace static story tile with RouterLink to `/stories/new`
- Optionally show 3 most recent stories with status pills below tiles

---

## Build Order

1. Config + dependency (Step 1)
2. Anthropic integration (Step 2) — standalone, no other deps
3. Schemas (Step 3) — standalone
4. Service (Step 4) — depends on schemas + models
5. Worker (Step 6) — depends on integration + service
6. Celery registration (Step 6)
7. API routes (Step 5) — depends on service + schemas
8. Register router in main.py (Step 5)
9. Backend tests (Step 7)
10. Frontend service (Step 8)
11. Frontend store (Step 9)
12. StoryCreateView (Step 10)
13. StoryDetailView (Step 11)
14. Router + Dashboard + CSS updates (Step 12)
15. Frontend tests

## Verification

1. **Backend unit tests:** `cd backend && uv run pytest tests/test_stories.py -v`
2. **All backend tests pass:** `cd backend && uv run pytest`
3. **Frontend build:** `cd frontend && npm run build` (no TS errors)
4. **Frontend tests:** `cd frontend && npm run test:unit`
5. **Manual E2E flow:**
   - Start infra: `docker compose up -d`
   - Start backend: `cd backend && uv run uvicorn app.main:app --reload --reload-dir app --reload-exclude '.venv/*'`
   - Start Celery: `cd backend && uv run celery -A app.tasks.celery_app worker --loglevel=info`
   - Start frontend: `cd frontend && npm run dev`
   - Login → Create a child → Navigate to Create Story → Fill form → Submit
   - Watch StoryDetailView poll and show pages appearing
   - Verify in DB: stories, story_pages, story_generation_jobs, story_page_generations rows created

## Related Docs

- [Build plan](./2026-03-11-build-plan.md) — Phase 9 section
- [Story generation pipeline](../story-generation.md) — async pipeline design, status models, page-level generation
- [Architecture](../architecture.md) — orchestrator and worker boundaries
- [Schema](../schema.md) — Story, StoryPage, StoryGenerationJob, StoryPageGeneration tables
- [Storage](../storage.md) — asset model, signed URLs (used by Phases 10-12 for images/audio)
- [Voice](../voice.md) — voice profile lifecycle (voice_profile_id is optional on story creation)
