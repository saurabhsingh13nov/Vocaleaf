Voice

This document describes the voice capture and voice cloning model for the storybook app.

It covers:
	•	the difference between voice_profiles and voice_samples
	•	raw voice sample upload flow
	•	clone lifecycle and status handling
	•	consent and privacy expectations
	•	how a story selects a narration voice
	•	provider abstraction rules

Goals

The voice system should support:
	•	parent-uploaded voice recordings
	•	explicit voice cloning consent
	•	creation of a reusable narration voice
	•	per-page narration audio generation
	•	private handling of raw voice recordings
	•	provider replacement without changing core product logic

Core distinction

Keep these two concepts separate:
	•	voice_profiles = usable narration voices
	•	voice_samples = raw uploaded recordings used to create a voice profile

Do not merge them.

Why the separation matters

voice_profiles

Represents the logical voice the product can actually use for narration.

A voice profile:
	•	belongs to one user
	•	may be linked to multiple stories
	•	may be created from one or more voice samples
	•	has a lifecycle independent from individual sample files
	•	may be deleted by the user along with all of its current samples

voice_samples

Represents the uploaded recordings used to create or improve a voice profile.

A voice sample:
	•	belongs to one user
	•	belongs to one voice_profile
	•	points to an asset row for the uploaded audio file
	•	stores metadata such as transcript, duration, quality score, and status
	•	may be deleted individually if the upload failed, is obsolete, or was added by mistake

Data model

voice_profiles

Important fields:
	•	id
	•	user_id
	•	provider
	•	provider_voice_id
	•	display_name
	•	clone_type
	•	status
	•	source_type
	•	consent_confirmed
	•	default_for_user
	•	created_at
	•	updated_at

Recommended meaning of status:
	•	pending = profile created but clone work not started
	•	processing = provider clone request in progress
	•	ready = usable for story narration
	•	failed = clone attempt failed or was rejected
	•	deleted = no longer selectable for new stories

voice_samples

Important fields:
	•	id
	•	user_id
	•	voice_profile_id
	•	asset_id
	•	duration_seconds
	•	transcript
	•	sample_quality_score
	•	status
	•	created_at

Recommended meaning of status:
	•	pending = upload initiated but not yet confirmed in storage
	•	uploaded = file accepted and recorded
	•	processing = validation or provider-side preparation in progress
	•	accepted = good sample for cloning
	•	rejected = sample failed validation or quality review

Current implementation status

Phases 7 and 8 currently ship:
	•	voice_profile creation and listing in the authenticated product UI
	•	required consent capture at voice_profile creation time via `consent_confirmed`
	•	browser recording via MediaRecorder and direct file upload as two sample-input paths
	•	duration capture during upload initiation
	•	private direct-to-storage uploads for raw voice samples
	•	user-initiated deletion for individual voice_samples, including pending uploads
	•	user-initiated deletion for whole voice_profiles with cascading sample removal
	•	clearer phase-7 UI labels for profile state: `Add samples` before uploads and `Awaiting clone` after successful sample collection
	•	manual clone initiation from the voice profiles UI once at least one sample has been confirmed
	•	Celery-backed clone execution using Redis and the official ElevenLabs Python SDK behind the integration boundary
	•	prefork-safe async worker session handling so clone jobs run correctly under the normal Celery worker pool
	•	profile-detail polling in the frontend until clone status reaches `ready` or `failed`
	•	stored `provider_voice_id` values that work for provider-side TTS even when the provider dashboard does not show a preview sample

Not shipped yet:
	•	separate `consents` table writes for voice cloning
	•	webhook-based provider completion handling
	•	provider-side deletion when a local voice_profile is deleted
	•	provider preview sample generation for dashboard playback
	•	raw sample playback/download in the normal user UI

Upload flow

Recommended voice sample upload flow:
	1.	authenticated frontend creates a voice_profile and records consent at that time
	2.	authenticated frontend requests a signed upload URL for a specific voice_profile
	3.	FastAPI verifies the user, validates MIME type/file size/duration, and creates an object key in a private voice-sample prefix
	4.	FastAPI creates pending `assets` and `voice_samples` rows linked to the target voice_profile
	5.	FastAPI returns a short-lived signed upload URL
	6.	browser uploads directly to object storage
	7.	frontend notifies backend that upload completed
	8.	backend verifies the object exists in storage and marks the asset ready and the sample uploaded

Why direct upload is preferred:
	•	keeps large files out of the API process
	•	scales better
	•	fits the generic asset model already used by the project

Consent requirements

Voice cloning requires explicit consent.

Minimum expectations:
	•	record consent before starting clone processing
	•	set voice_profiles.consent_confirmed only after consent is captured
	•	store a matching consent record for voice cloning when the consent/audit phase lands
	•	do not allow clone processing for a profile without confirmed consent

The system should assume voice data is highly sensitive.

Privacy rules

Raw voice samples are the most sensitive asset tier in the product.

Required handling:
	•	private buckets only
	•	short-lived signed upload URLs
	•	no public bucket access
	•	no routine direct read access in the normal product UI
	•	backend-only or tightly controlled access for admin/compliance workflows

The database stores only metadata. Raw audio bytes remain in object storage.

Clone lifecycle

Recommended lifecycle:
	1.	user creates a voice_profile
	2.	user uploads one or more voice_samples
	3.	system validates sample presence, duration, and basic quality
	4.	system confirms consent exists
	5.	user explicitly starts clone processing from the UI
	6.	background worker submits clone request to the configured provider
	7.	voice_profile moves to processing
	8.	on success, provider_voice_id is stored and voice_profile moves to ready
	9.	on failure, voice_profile moves to failed with enough metadata in logs for debugging

Important rule:
	•	clone work belongs in background workers, not synchronous API requests

Story voice selection

Stories may optionally reference a voice_profile_id.

Selection rules:
	•	a story may use a specific ready voice_profile chosen by the user
	•	if the product later supports a default voice, it should come from voice_profiles.default_for_user
	•	a story must not use a voice_profile unless its status is ready

Narration generation

Audio generation should happen per page, not only as one full-story file.

Why:
	•	fits the story_pages model
	•	supports page-level retries
	•	allows partial regeneration
	•	keeps playback flexible in the reader UI

Each generated page narration should be stored as:
	•	an assets row for the audio file
	•	a story_pages.audio_asset_id reference
	•	optional duration metadata on story_pages.duration_ms

Provider abstraction

Provider-specific code should live behind integrations and services, not inside API routes or ORM models.

The provider layer should own:
	•	clone request submission
	•	provider_voice_id handling
	•	readiness polling or webhook handling
	•	TTS generation for page narration
	•	provider-specific request and response mapping

The core domain model should stay provider-neutral.

Failure and retry expectations

Design voice operations for retries.

Examples:
	•	provider clone request transiently fails
	•	uploaded sample quality is too low
	•	audio generation fails for a single story page

Retries should:
	•	target the failed unit of work
	•	record enough metadata for debugging
	•	not require deleting and recreating unrelated records

Related docs

For adjacent topics, see:
	•	auth.md for user/account identity
	•	storage.md for signed URL and privacy rules
	•	schema.md for the underlying tables
	•	story-generation.md for page audio generation in the broader pipeline
