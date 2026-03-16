[Home](Home) | [Product Tour](Product-Tour) | [Privacy and Trust](Privacy-and-Trust)

# Technical Approach

Vocaleaf is built as a modular monolith with background workers. The goal is to keep the first real version simple to deploy and easy to debug while still supporting AI-heavy workflows, private media storage, and page-level retries.

## Stack

| Layer | Current approach |
| --- | --- |
| Frontend | Vue 3, Vite, TypeScript, Pinia, Tailwind CSS |
| Backend | FastAPI, SQLAlchemy 2.0 async, Alembic |
| Database | PostgreSQL |
| Queue and workers | Redis + Celery |
| Storage | Private S3-compatible object storage |
| AI providers | Anthropic for story text, Gemini for images, ElevenLabs for voice cloning and TTS |

## System shape

```text
Browser UI
  -> FastAPI API
     -> PostgreSQL for app state and metadata
     -> Object storage for image/audio/sample bytes
     -> Redis queue for long-running work
        -> Celery workers for text, image, audio, and voice clone jobs
```

## Why the architecture looks like this

API requests should validate input, persist state, enqueue work, and return quickly. Story text, image generation, narration audio, and voice cloning are all asynchronous because they are slow, failure-prone, and expensive enough to deserve explicit retries and status tracking.

This approach keeps the user-facing product responsive while making each long-running step observable and replaceable.

## Core modeling choices

| Modeling rule | Why it matters |
| --- | --- |
| `users` and `auth_identities` are separate | One account can support password and OAuth sign-in without collapsing identity and auth concerns together. |
| `voice_profiles` and `voice_samples` are separate | A reusable narration voice is not the same thing as the raw recordings used to create it. |
| `stories` and `story_pages` are separate | Story generation, playback, and retries all work better when pages are first-class records. |
| `assets` stores metadata only | Postgres stays focused on state while file bytes live in object storage. |

## Generation pipeline

1. The API creates the story record and generation job.
2. A text worker produces structured page output.
3. An image worker generates private illustrations page by page.
4. If the story has a ready narration voice, an audio worker generates per-page narration.
5. The story becomes ready when all required outputs are complete.

Because each page is tracked independently, the system can preserve successful work and retry only missing or failed outputs.

## Engineering qualities the project optimizes for

- Replaceable provider boundaries instead of provider logic leaking into routes and models
- Explicit status fields over hidden workflow assumptions
- Retry-friendly workers for each generation modality
- Signed media access instead of public buckets
- A domain model that reflects the product clearly enough to evolve without major rewrites
