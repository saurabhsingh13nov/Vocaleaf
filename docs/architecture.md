Architecture

This document describes the current target system architecture for the personalized storybook app.

Goals

The system should support:
	•	parent accounts with email/password and OAuth login
	•	child profiles for personalization
	•	voice sample uploads and cloned parent narration
	•	AI-generated story text
	•	AI-generated page illustrations
	•	per-page narration audio
	•	private storage for all generated and uploaded assets
	•	asynchronous generation with retries and observability

Architectural style

Recommended v1 approach:
	•	modular monolith for the backend
	•	asynchronous workers for long-running AI tasks
	•	PostgreSQL as the source of truth for metadata and state
	•	object storage for images, audio, and raw uploads
	•	Redis-backed job queue for orchestration and retries

Avoid premature microservices. The first production version should remain simple to deploy and easy to debug.

High-level system diagram

┌─────────────────────────────────────────────────────────────────────────────┐
│                                CLIENT LAYER                                │
├─────────────────────────────────────────────────────────────────────────────┤
│ Web App (Vue.js / React)                                                  │
│ - signup/login                                                             │
│ - child profiles                                                           │
│ - voice sample upload                                                      │
│ - story creation                                                           │
│ - story reader                                                             │
└───────────────────────────────┬─────────────────────────────────────────────┘
                                │ HTTPS
                                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              EDGE / DELIVERY                               │
├─────────────────────────────────────────────────────────────────────────────┤
│ CDN / Reverse Proxy / Load Balancer                                        │
│ - TLS termination                                                          │
│ - static asset delivery                                                    │
│ - routing                                                                  │
└───────────────────────────────┬─────────────────────────────────────────────┘
                                │
                ┌───────────────┴────────────────┐
                │                                │
                ▼                                ▼
┌──────────────────────────────┐    ┌───────────────────────────────────────┐
│        FRONTEND APP          │    │          FASTAPI BACKEND             │
├──────────────────────────────┤    ├───────────────────────────────────────┤
│ UI, routing, playback        │    │ API, auth, validation, orchestration │
└──────────────┬───────────────┘    └───────────────┬───────────────────────┘
               │                                    │
               │                                    ▼
               │                     ┌───────────────────────────────────────┐
               │                     │           CORE API MODULES            │
               │                     ├───────────────────────────────────────┤
               │                     │ Auth & Identity                       │
               │                     │ User / Child Profiles                 │
               │                     │ Voice Profiles                        │
               │                     │ Story Service                         │
               │                     │ Asset Service                         │
               │                     │ Subscription / Usage                  │
               │                     │ Consent / Audit                       │
               │                     └───────────────┬───────────────────────┘
               │                                     │
               │                                     ▼
               │                     ┌───────────────────────────────────────┐
               │                     │         ORCHESTRATION LAYER           │
               │                     ├───────────────────────────────────────┤
               │                     │ Story Generation Orchestrator         │
               │                     │ - create job                          │
               │                     │ - split page work                     │
               │                     │ - dispatch tasks                      │
               │                     │ - collect results                     │
               │                     │ - update story/page states            │
               │                     └───────────────┬───────────────────────┘
               │                                     │
               │                                     ▼
               │                     ┌───────────────────────────────────────┐
               │                     │         QUEUE / CACHE LAYER           │
               │                     ├───────────────────────────────────────┤
               │                     │ Redis + Celery                        │
               │                     │ - async jobs                          │
               │                     │ - retries                             │
               │                     │ - transient coordination              │
               │                     └───────┬───────────────┬───────────────┘
               │                             │               │
               ▼                             ▼               ▼
┌──────────────────────────────┐  ┌────────────────┐  ┌─────────────────────┐
│     OBJECT STORAGE           │  │ TEXT WORKER    │  │ IMAGE WORKER         │
├──────────────────────────────┤  ├────────────────┤  ├─────────────────────┤
│ private buckets              │  │ story outline  │  │ page illustrations   │
│ voice samples                │  │ page text JSON │  │ provider adapter     │
│ story images                 │  └────────────────┘  └─────────────────────┘
│ narration audio              │
│ cover images                 │  ┌────────────────┐  ┌─────────────────────┐
└──────────────────────────────┘  │ AUDIO WORKER   │  │ POST-PROCESS WORKER  │
                                  ├────────────────┤  ├─────────────────────┤
                                  │ TTS + cloning  │  │ metadata, thumbnails │
                                  │ per-page audio │  │ cleanup, transforms  │
                                  └────────────────┘  └─────────────────────┘

                                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                                DATA LAYER                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│ PostgreSQL                                                                  │
│ - users, auth_identities                                                    │
│ - children                                                                  │
│ - voice_profiles, voice_samples                                             │
│ - stories, story_pages                                                      │
│ - assets                                                                    │
│ - generation jobs                                                           │
│ - subscriptions, usage, consents, audit                                     │
└─────────────────────────────────────────────────────────────────────────────┘

                                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         EXTERNAL INTEGRATIONS                               │
├─────────────────────────────────────────────────────────────────────────────┤
│ OAuth providers                                                             │
│ Text generation provider                                                    │
│ Image generation provider                                                   │
│ Voice provider                                                              │
│ Billing provider                                                            │
│ Email provider                                                              │
└─────────────────────────────────────────────────────────────────────────────┘

Core modules

1. Frontend app

The frontend is responsible for user interaction only.

Primary responsibilities:
	•	authentication flows
	•	child profile management UI
	•	story creation form
	•	voice upload UX
	•	story playback UI
	•	polling or subscribing to generation status

It should not contain business-critical logic. Validation and authorization belong in the backend.

2. FastAPI backend

The backend is the main control plane.

Responsibilities:
	•	API routing
	•	authentication and authorization
	•	persistence to Postgres
	•	issuing signed upload/download URLs
	•	creating generation jobs
	•	exposing story state and results
	•	calling internal service modules

The backend should remain fast and mostly non-blocking. Long-running generation should always move to workers.

3. Auth and identity module

This module manages account and login concerns.

Responsibilities:
	•	user account creation
	•	password login
	•	OAuth login
	•	linking auth identities to users
	•	email verification
	•	password reset
	•	session or token issuance

Key modeling rule:
	•	users stores the account
	•	auth_identities stores login methods

4. User and child profile module

This module stores personalization inputs.

Responsibilities:
	•	parent profile information
	•	child profiles
	•	interests, favorite themes, preferences
	•	profile retrieval and updates

These profiles feed generation prompts and story personalization.

5. Voice profile module

This module manages voice capture and cloning.

Responsibilities:
	•	accepting voice sample uploads
	•	storing metadata for raw uploaded audio
	•	creating voice clone requests
	•	tracking clone lifecycle and readiness
	•	selecting the active narration voice for a story

Important separation:
	•	voice_samples are raw inputs
	•	voice_profiles are usable cloned voices

6. Story service

This module owns story creation and retrieval.

Responsibilities:
	•	create story drafts
	•	store user prompt and story settings
	•	fetch stories and story pages
	•	request page regeneration
	•	connect story records to assets and jobs

This is the primary domain service for the product.

7. Asset service

This module manages file metadata and access.

Responsibilities:
	•	create asset metadata rows
	•	issue signed upload URLs
	•	issue signed read URLs
	•	validate file ownership rules
	•	track storage provider, object key, MIME type, size, duration, dimensions

Files should never be stored in Postgres. Only metadata belongs in the database.

8. Story generation orchestrator

This is the workflow coordinator for the AI pipeline.

Responsibilities:
	•	create a generation job
	•	produce a structured page plan
	•	dispatch image and audio generation tasks
	•	update story and page statuses
	•	collect outputs and finalize story state

This should be the single place that coordinates multi-step generation.

9. Queue / worker system

This supports asynchronous execution.

Responsibilities:
	•	enqueue long-running tasks
	•	retry transient failures
	•	isolate slow or provider-dependent work from API requests
	•	support page-level regeneration

Typical task types:
	•	full story generation
	•	page image generation
	•	page audio generation
	•	voice clone creation
	•	asset post-processing

10. Text worker

This worker generates story text and structure.

Responsibilities:
	•	title generation
	•	page outline generation
	•	final narration text per page
	•	image prompt generation
	•	continuity notes and structured output

Expected output:
	•	normalized JSON suitable for downstream image and audio workers

11. Image worker

This worker creates illustrations.

Responsibilities:
	•	consume page prompt + continuity context
	•	call image provider
	•	store generated images in object storage
	•	create assets rows
	•	attach image assets to story_pages

Current implementation note:
	•	the image worker uses Google Gemini image-generation models through the Google GenAI SDK `generate_content()` flow

The system should support rerunning just one page if necessary.

12. Audio worker

This worker creates narration audio. Voice cloning remains a separate worker.

Responsibilities:
	•	synthesize narration using selected voice profile
	•	generate audio per page
	•	store audio in object storage
	•	update page duration and linked audio asset
	•	finalize narrated stories once all pages are complete

Audio should be page-based for better playback control and cheaper retries.

13. Post-process worker

Optional but useful early.

Responsibilities:
	•	create thumbnails or alternate sizes
	•	compute media metadata
	•	compress or transform assets
	•	cleanup expired temporary files
	•	run moderation hooks if needed

14. PostgreSQL

This is the source of truth for product state.

It stores:
	•	users and auth identities
	•	children
	•	voice profiles and voice samples
	•	stories and story pages
	•	assets metadata
	•	generation jobs
	•	plans, subscriptions, usage, consents, audit events

It should not store raw binary file data.

15. Object storage

This stores all file bytes.

It stores:
	•	raw voice sample uploads
	•	generated page images
	•	generated page audio
	•	cover images
	•	thumbnails or derived files

Buckets should be private. Access should generally happen via short-lived signed URLs.

16. External integrations

These are replaceable adapters to third-party systems.

Examples:
	•	Google / Apple OAuth
	•	text model provider
	•	image generation provider
	•	voice generation provider
	•	Stripe or other billing provider
	•	email delivery provider

Provider-specific code should be isolated behind service interfaces.

17. Consent and audit module

This module protects sensitive operations.

Responsibilities:
	•	record voice cloning consent
	•	record privacy / terms acceptance
	•	log key account and content actions
	•	support support/compliance workflows

This is especially important because the product involves child-related content and cloned parent voices.

18. Usage and subscription module

This module handles monetization and internal cost visibility.

Responsibilities:
	•	active subscription lookup
	•	feature gating
	•	quotas and plan checks
	•	metered usage recording
	•	cost tracking by provider

This should exist early even if billing launches later.

19. Observability and operations

This module is not user-facing but is required for production reliability.

Responsibilities:
	•	structured logs
	•	request tracing
	•	job status dashboards
	•	metrics and alerts
	•	provider failure tracking
	•	queue depth visibility

Without this layer, async generation systems become difficult to debug.

Request flows

Signup and login flow

User -> Frontend -> FastAPI Auth
     -> Password verification OR OAuth provider exchange
     -> users/auth_identities lookup or creation
     -> session/token issued

Voice clone setup flow

User -> Frontend -> FastAPI
     -> request signed upload URL
     -> upload sample to object storage
     -> create asset + voice_sample rows
     -> enqueue voice clone task
     -> worker calls voice provider
     -> voice_profile updated to ready/failed

Story generation flow

User -> Frontend -> FastAPI Story API
     -> create story + generation job
     -> enqueue full story generation task
     -> text worker generates page plan + page text
     -> image worker generates page illustrations
     -> audio worker generates page narration
     -> assets stored + story_pages updated
     -> story marked ready or failed

Story playback flow

User -> Frontend -> FastAPI
     -> auth + ownership check
     -> short-lived signed URLs returned
     -> browser loads images/audio directly from object storage

Deployment recommendation for v1

Start with a simple deployment shape:
	•	1 frontend service
	•	1 FastAPI service
	•	1 worker service
	•	1 PostgreSQL instance
	•	1 Redis instance
	•	1 object storage setup

You can split worker responsibilities later if scale or provider-specific load requires it.

Design principles

Keep API synchronous, generation asynchronous

The API should validate input, persist metadata, enqueue work, and return quickly.

Store metadata in Postgres, bytes in object storage

Do not place generated images, audio, or voice samples directly in the relational database.

Make generation retryable at the page level

A single failed page should not force regeneration of the entire story.

Keep providers replaceable

Use integration adapters so you can swap image, text, voice, billing, or email providers later.

Treat voice samples and story assets as private by default

Use private buckets and short-lived signed URLs.

Prefer explicit workflow state

Track jobs and statuses directly rather than inferring state from missing fields.

Current recommended defaults

Unless a later decision changes them, assume:
	•	FastAPI backend
	•	PostgreSQL database
	•	Redis for queue/cache
	•	object storage for all assets
	•	private buckets only
	•	signed URLs for asset access
	•	asynchronous generation pipeline
	•	modular monolith architecture

Out of scope for v1

Avoid adding these too early:
	•	microservice decomposition
	•	collaborative editing
	•	multi-parent family account models
	•	complex access control layers for shared stories
	•	synchronous in-request generation of large media assets
