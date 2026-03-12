Purpose: provide precise, agent-focused guidance for working in this codebase. This file complements the main README.md and the detailed docs under docs/.

Project at a glance

This project is a web app for personalized children’s storybooks with:
	•	parent accounts and child profiles
	•	custom story generation
	•	AI-generated illustrations
	•	cloned parent voice narration
	•	private storage for story assets and voice samples

Current backend preference:
	•	FastAPI (Python)

Current architectural direction:
	•	FastAPI monolith + worker(s) + Postgres + Redis + object storage

Source of truth docs

Read these before making meaningful changes:
	•	README.md — setup, local development, product summary
	•	docs/architecture.md — system modules, boundaries, request flows, async workers
	•	docs/schema.md — ER model, SQLAlchemy entities, relationships, constraints
	•	docs/auth.md — user/auth model, OAuth + password strategy, session/token approach
	•	docs/story-generation.md — story pipeline, generation job lifecycle, page generation rules
	•	docs/storage.md — asset storage model, signed URLs, retention, privacy expectations
	•	docs/voice.md — voice sample flow, cloning lifecycle, consent requirements

If any of these docs do not exist yet, create them before introducing major new code paths.

Core product concepts

Keep these distinctions clear:

1. User vs auth identity
	•	users represents the app account.
	•	auth_identities represents how the user logs in.
	•	One user may have multiple auth identities.
	•	OAuth identities do not have password hashes.
	•	Password identities store only password_hash.

2. Voice profile vs voice sample
	•	voice_profiles are usable narration voices.
	•	voice_samples are raw uploaded recordings used to create a voice profile.
	•	Do not merge these concepts.

3. Story vs story page
	•	stories is the top-level story object.
	•	story_pages contains page-level text and linked assets.
	•	Each page may have separate image/audio assets.

4. Asset metadata vs file bytes
	•	assets stores metadata only.
	•	Actual files live in object storage.
	•	Do not store raw image/audio bytes in Postgres.

5. Sync API vs async generation
	•	API requests should validate, persist, enqueue, and return.
	•	Long-running AI generation must run in background workers.
	•	Do not block API requests on image/audio generation.

Engineering rules

Architecture
	•	Prefer a modular monolith over premature microservices.
	•	Keep provider-specific logic behind service interfaces.
	•	Separate API orchestration from generation workers.
	•	Make page-level regeneration possible.

Data modeling
	•	Prefer explicit state fields over hidden workflow assumptions.
	•	Use UUID primary keys.
	•	Track timestamps consistently.
	•	Use enums for controlled lifecycle/status fields.
	•	Keep assets generic instead of creating many file tables.

Security and privacy
	•	Treat voice samples as highly sensitive.
	•	Keep storage buckets private.
	•	Use short-lived signed URLs for private asset access.
	•	Never make raw voice samples publicly accessible.
	•	Record explicit consent for voice cloning.
	•	Use Argon2id for password hashing.
	•	Do not add a separate password salt column.

Story generation
	•	Generate structured story output, not loose free-form blobs.
	•	Preserve continuity across pages using reusable context.
	•	Generate audio per page, not only one full-story file.
	•	Store the final page text separately from prompts.

Reliability
	•	Track generation jobs explicitly.
	•	Design every generation step for retries.
	•	Make providers replaceable.
	•	Record enough metadata for debugging failed runs.

Expected directory layout

Suggested target structure:

app/
  api/
  core/
  db/
  models/
  schemas/
  services/
  workers/
  tasks/
  integrations/
  utils/

docs/
  architecture.md
  schema.md
  auth.md
  storage.md
  voice.md
  story-generation.md

alembic/

tests/

Backend module ownership

app/models/

SQLAlchemy ORM models only.

app/schemas/

Pydantic request/response models.

app/services/

Business logic and orchestration helpers.
Examples:
	•	auth service
	•	signed URL service
	•	story creation service
	•	voice profile service

app/integrations/

External provider wrappers.
Examples:
	•	Google OAuth
	•	ElevenLabs
	•	image provider
	•	billing provider

app/workers/ or app/tasks/

Background generation jobs.
Examples:
	•	full story generation
	•	page image generation
	•	page audio generation
	•	voice clone processing

Agent workflow guidance

When working on a task:
	1.	Read the relevant doc in docs/ first.
	2.	Identify whether the task affects API, schema, workers, or provider integrations.
	3.	Update docs when changing architecture, schema, or flows.
	4.	Prefer small, reviewable changes.
	5.	Preserve naming consistency across ORM models, migrations, and API schemas.

Naming conventions

Use consistent names across code and docs:
	•	user, auth_identity
	•	child
	•	voice_profile, voice_sample
	•	story, story_page
	•	asset
	•	story_generation_job, story_page_generation
	•	subscription, plan, usage_record, consent, audit_event

Avoid introducing alternate terms for the same concept.

Questions to resolve before major implementation

These decisions should be explicit in docs before coding deep integrations:
	•	session strategy: cookie session vs JWT
	•	job system: Celery vs Dramatiq vs RQ
	•	object storage choice: S3 vs R2 vs other S3-compatible
	•	image provider choice for v1
	•	auth library strategy in FastAPI
	•	billing timing: now vs later

Current recommended defaults

Unless docs say otherwise, assume:
	•	FastAPI backend
	•	PostgreSQL database
	•	Redis for queue/cache
	•	object storage for all binary assets
	•	private buckets only
	•	signed URLs for asset access
	•	OAuth + password auth supported
	•	Argon2id for password hashing
	•	story generation is asynchronous

Documentation rule

If you change one of these, update the matching doc:
	•	system design → docs/architecture.md
	•	data model → docs/schema.md
	•	auth/login/account model → docs/auth.md
	•	storage and asset access → docs/storage.md
	•	voice cloning flow → docs/voice.md
	•	generation pipeline → docs/story-generation.md