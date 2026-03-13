Story Generation

This document describes the story generation pipeline for the storybook app.

It covers:
	•	how a story request becomes an async job
	•	how text, image, and audio generation are split
	•	page-level generation and regeneration
	•	state transitions for stories, pages, and jobs
	•	retry expectations and failure handling
	•	what should be stored in story and generation tables

Goals

The story generation system should support:
	•	personalized story creation for a child
	•	structured page output rather than one free-form blob
	•	AI-generated illustrations per page
	•	per-page narration audio
	•	page-level retries and regeneration
	•	provider replacement without rewriting the product domain model

Core design rule

Story generation is asynchronous.

API requests should:
	•	validate input
	•	create or update database records
	•	create a story_generation_job
	•	enqueue background work
	•	return quickly

API requests should not block on text, image, or audio generation.

Top-level entities

stories

Represents the top-level story record.

This table stores:
	•	ownership
	•	child association
	•	selected voice_profile
	•	title and prompt inputs
	•	story-level configuration such as page count, language, and art style
	•	top-level status

story_pages

Represents one page of a story.

This table stores:
	•	page_number
	•	final text_content
	•	image_prompt
	•	continuity_notes
	•	image_asset_id
	•	audio_asset_id
	•	duration_ms
	•	page status

story_generation_jobs

Represents one async workflow execution for a story.

Use this table to track:
	•	job type
	•	provider choices
	•	retry count
	•	error message
	•	started_at and completed_at
	•	overall workflow status

Do not try to represent the full async workflow using only stories.status.

story_page_generations

Represents one generation attempt for one page and one modality.

Use this table to track:
	•	which page was generated
	•	which story_generation_job triggered it
	•	generation_type such as text, image, or audio
	•	provider used
	•	request and response payload metadata
	•	prompt version
	•	attempt status

Generation flow

Recommended full-story flow:
	1.	user submits story creation input for a child
	2.	FastAPI validates ownership and request shape
	3.	FastAPI creates a stories row in draft or generating state
	4.	FastAPI creates a story_generation_job row
	5.	FastAPI enqueues the orchestrator job and returns
	6.	orchestrator creates the structured page plan
	7.	orchestrator creates or updates story_pages rows
	8.	text generation finalizes page text and image prompts
	9.	image generation creates page illustrations
	10.	audio generation creates per-page narration audio
	11.	orchestrator finalizes statuses when all required page work completes

The orchestrator should be the single workflow coordinator for multi-step generation.

Structured output expectations

Do not store generation as one loose text blob.

The pipeline should produce structured page data including:
	•	page order
	•	final page text
	•	image prompt or illustration instructions
	•	continuity notes needed for later pages

The final page text should be stored in story_pages.text_content, not only inside prompts or provider responses.

Continuity model

Story continuity must be preserved across pages.

Recommended approach:
	•	generate an overall story plan or outline first
	•	reuse stable story context across later page requests
	•	store page-specific continuity guidance in story_pages.continuity_notes
	•	use story_characters and character_profiles when character consistency matters

This allows page regeneration without losing the larger narrative frame.

Status model

Recommended story status usage:
	•	draft = story exists but generation has not started
	•	generating = async work is in progress
	•	ready = all required story outputs are complete
	•	failed = the workflow failed and needs retry or intervention
	•	deleted = no longer active

Current implementation note for phase 9:
	•	text generation is the only required output today, so stories transition to ready when text generation completes successfully
	•	story_pages remain at text_ready until later image/audio phases are implemented

Recommended page status usage:
	•	pending = page exists but generation has not produced usable output yet
	•	text_ready = final text is stored
	•	image_ready = image asset is ready
	•	audio_ready = audio asset is ready
	•	complete = page has all required outputs
	•	failed = page-level work failed

Recommended job status usage:
	•	pending
	•	running
	•	completed
	•	failed
	•	cancelled

Page-level generation

Pages are first-class units of work.

That means:
	•	text generation can fail for one page without losing the whole story record
	•	image generation can be retried for one page
	•	audio generation can be retried for one page
	•	a user-facing regeneration action can target one page instead of restarting everything

Page-level generation attempts should create story_page_generations records per modality.

Image generation

Each page illustration should:
	•	be generated asynchronously
	•	produce a private asset in object storage
	•	create or update an assets row
	•	set story_pages.image_asset_id when ready

Prompt inputs should use:
	•	the page text
	•	story-wide context
	•	continuity notes
	•	art style and character consistency inputs

Audio generation

Each page narration should:
	•	be generated asynchronously
	•	use the selected ready voice_profile if narration is enabled
	•	produce a private audio asset in object storage
	•	set story_pages.audio_asset_id when ready
	•	optionally update story_pages.duration_ms

Do not limit narration to one full-story output file.

Regeneration rules

The system should support:
	•	full story generation
	•	full story retry after failure
	•	page text regeneration
	•	page image regeneration
	•	page audio regeneration

Regeneration should preserve unaffected pages and assets unless the user explicitly requests broader replacement behavior.

Failure handling

The system should record enough metadata to debug failures.

Examples:
	•	provider error payloads
	•	retry counts
	•	job and page timestamps
	•	modality-specific failure states

If one modality fails:
	•	the relevant story_page should reflect the failure
	•	the story_generation_job should reflect that the workflow is incomplete or failed
	•	unrelated completed outputs should remain attached to the story unless intentionally replaced

Provider boundaries

Provider-specific logic belongs behind integrations and workers.

The core services should coordinate:
	•	story creation
	•	job creation
	•	page record creation
	•	status updates
	•	retry orchestration

The provider layer should own:
	•	request formatting
	•	response parsing
	•	provider-specific retries or polling

Storage expectations

Generated files should follow the generic asset model.

Typical outputs:
	•	cover images
	•	page images
	•	page audio
	•	optional derived assets such as thumbnails

All generated media should be private by default and served through short-lived signed URLs after auth and ownership checks.

Related docs

For adjacent topics, see:
	•	architecture.md for orchestrator and worker boundaries
	•	schema.md for table definitions
	•	storage.md for asset storage and signed URL access
	•	voice.md for cloned narration voice behavior
