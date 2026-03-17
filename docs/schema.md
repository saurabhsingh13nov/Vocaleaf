Schema

This document describes the current data model for the storybook app.

It covers:
	•	domain entities
	•	relationships
	•	why certain entities are separate
	•	which tables are required for v1
	•	how the schema supports voice cloning, story generation, storage, and billing

Design principles

The schema is designed around a few core ideas:
	•	keep app account identity separate from authentication methods
	•	keep raw uploaded files separate from usable logical resources
	•	keep file bytes outside Postgres
	•	model stories and pages explicitly
	•	support async generation and retries
	•	support monetization and auditability early

Core entity groups

The schema can be understood as six groups:
	•	identity and auth
	•	family profiles
	•	voice system
	•	story system
	•	file/assets system
	•	operations, billing, and compliance

High-level ER model

User
 ├── AuthIdentity
 ├── Child
 │    └── Story
 │         ├── StoryPage
 │         │    ├── image Asset
 │         │    └── audio Asset
 │         ├── StoryGenerationJob
 │         └── StoryCharacter
 ├── VoiceProfile
 │    └── VoiceSample
 │         └── Asset
 ├── Asset
 ├── Subscription
 ├── Consent
 ├── AuditEvent
 └── UsageRecord

Plan
 └── Subscription

CharacterProfile
 └── StoryCharacter

Tables by importance

Must-have tables

These are the minimum core product tables:
	•	users
	•	auth_identities
	•	children
	•	voice_profiles
	•	voice_samples
	•	assets
	•	stories
	•	story_pages

Strongly recommended tables

These should be included early because they simplify production operation:
	•	story_generation_jobs
	•	plans
	•	subscriptions
	•	consents

Nice to add early tables

These improve debugging, scale readiness, analytics, and consistency:
	•	story_page_generations
	•	character_profiles
	•	story_characters
	•	audit_events
	•	usage_records

Identity and auth

users

Represents the app account.

This table owns the product data:
	•	child profiles
	•	stories
	•	voice profiles
	•	subscriptions
	•	assets

It is intentionally separate from authentication methods.

Important fields:
	•	id
	•	primary_email
	•	full_name
	•	avatar_url
	•	status
	•	role
	•	email_verified_at
	•	last_login_at
	•	created_at
	•	updated_at

Current implementation note:
	•	`role` is a FK-backed role code used for internal authorization: `customer`, `staff`, `admin`

user_roles

Represents the database-backed catalog of valid app roles.

Important fields:
	•	code
	•	display_name
	•	description
	•	created_at
	•	updated_at

Current implementation note:
	•	`users.role` references `user_roles.code`
	•	the app currently seeds `customer`, `staff`, and `admin`

auth_identities

Represents a sign-in method attached to a user.

Examples:
	•	email/password
	•	Google OAuth
	•	Apple OAuth

Why it exists:
	•	one user may have more than one login method
	•	OAuth users do not have local passwords
	•	authentication concerns should not clutter the users table

Important fields:
	•	id
	•	user_id
	•	provider
	•	provider_user_id
	•	email
	•	password_hash
	•	is_primary
	•	is_verified
	•	last_login_at
	•	created_at

Important rules:
	•	password identities store password_hash
	•	OAuth identities store provider_user_id
	•	password hashes should use Argon2id or equivalent
	•	no separate password salt column is needed

Family profiles

children

Represents a child profile used for personalization.

A child belongs to one user and may have many stories.

Important fields:
	•	id
	•	user_id
	•	name
	•	age
	•	favorite_themes
	•	favorite_characters
	•	bedtime_preferences
	•	created_at
	•	updated_at

This table allows story prompts to be personalized by age, preferences, and recurring themes.

Voice system

voice_profiles

Represents a usable narration voice.

This is the voice the system can actually use to synthesize audio for stories.

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

Why it is separate from voice_samples:
	•	a usable voice profile is a logical resource
	•	a voice profile can be created from multiple samples
	•	raw samples may later be deleted or retained separately

voice_samples

Represents raw uploaded recordings used to create a cloned voice.

A user may upload multiple voice samples for one voice profile.

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

This table should only store metadata about the sample. The actual file is referenced through asset_id.

File and asset system

assets

Represents metadata for files stored in object storage.

This is intentionally generic.

The table may represent:
	•	page images
	•	page audio
	•	voice sample uploads
	•	cover images
	•	thumbnails

Important fields:
	•	id
	•	user_id
	•	storage_provider
	•	bucket_name
	•	object_key
	•	asset_type
	•	upload_status
	•	mime_type
	•	file_size_bytes
	•	checksum
	•	width
	•	height
	•	duration_ms
	•	is_private
	•	confirmed_at
	•	created_at
	•	deleted_at

Why generic assets are better than many file tables:
	•	simpler storage model
	•	reusable across story pages, voice samples, and covers
	•	easier to support multiple storage providers

Important rule:
	•	Postgres stores only metadata
	•	object storage stores file bytes
	•	asset upload state should be explicit rather than inferred from missing metadata

Story system

stories

Represents the top-level story record.

A story belongs to one user, one child, and optionally one narration voice profile.

Important fields:
	•	id
	•	user_id
	•	child_id
	•	voice_profile_id
	•	cover_asset_id
	•	title
	•	prompt
	•	theme
	•	status
	•	target_page_count
	•	reading_level
	•	language
	•	art_style
	•	generation_version
	•	created_at
	•	updated_at

A story should be treated as the container for all page-level content.

story_pages

Represents one page within a story.

Each page may have:
	•	text content
	•	an image prompt
	•	one illustration asset
	•	one narration audio asset

Important fields:
	•	id
	•	story_id
	•	page_number
	•	text_content
	•	image_prompt
	•	continuity_notes
	•	image_asset_id
	•	audio_asset_id
	•	duration_ms
	•	status
	•	created_at
	•	updated_at

Why pages are first-class entities:
	•	page-level generation retries are necessary
	•	playback works page by page
	•	image and audio are naturally page-level assets
	•	text and prompts should be retained independently

Important constraint:
	•	(story_id, page_number) should be unique

Operations and generation

story_generation_jobs

Tracks asynchronous generation workflows.

This table is strongly recommended because story generation is multi-step and failure-prone.

Important fields:
	•	id
	•	story_id
	•	job_type
	•	status
	•	provider_text
	•	provider_image
	•	provider_audio
	•	retry_count
	•	error_message
	•	started_at
	•	completed_at
	•	created_at

This table makes it possible to:
	•	retry failed jobs
	•	understand workflow state
	•	separate API state from worker state
	•	debug provider-specific failures

story_page_generations

Tracks one generation attempt for one page and one modality.

This is very useful once the product supports page-level regeneration.

Important fields:
	•	id
	•	story_page_id
	•	generation_job_id
	•	generation_type
	•	provider
	•	request_payload_json
	•	response_payload_json
	•	prompt_version
	•	status
	•	created_at
	•	completed_at

This table helps compare retries, prompts, and provider results over time.

Character continuity system

character_profiles

Represents reusable character definitions.

Examples:
	•	the child
	•	a recurring teddy bear
	•	a pet dog
	•	a parent figure

Important fields:
	•	id
	•	user_id
	•	child_id
	•	reference_asset_id
	•	name
	•	role
	•	visual_description
	•	style_notes
	•	canonical_traits_json
	•	created_at
	•	updated_at

These profiles help keep generated illustrations consistent across pages and stories.

story_characters

Join table connecting stories to character profiles.

Important fields:
	•	id
	•	story_id
	•	character_profile_id
	•	role_in_story
	•	created_at

This allows:
	•	one story to include many characters
	•	one character profile to appear in many stories

Billing and product access

plans

Represents product tier definitions.

Important fields:
	•	id
	•	code
	•	name
	•	monthly_story_limit
	•	max_pages_per_story
	•	image_quality_mode
	•	voice_clone_limit
	•	monthly_audio_chars_limit
	•	price_cents
	•	active
	•	created_at

Current seeded defaults:
	•	`free` = 3 stories per period, 6 pages per story, 1 voice clone, 15,000 narration characters
	•	`premium` = 30 stories per period, 10 pages per story, 5 voice clones, 300,000 narration characters

Current implementation note:
	•	`code` is the stable identifier used by services and admin APIs
	•	the database row is the source of truth for base limits; bootstrap only creates missing plan rows and backfills missing codes

subscriptions

Represents the user’s active or historical subscription state.

Important fields:
	•	id
	•	user_id
	•	plan_id
	•	provider
	•	provider_subscription_id
	•	status
	•	current_period_start
	•	current_period_end
	•	cancel_at
	•	created_at
	•	updated_at

This allows feature gating and entitlement checks.

Current implementation note:
	•	new accounts receive an auto-assigned `free` subscription period
	•	before Stripe exists, plan changes happen through an internal CLI or admin API that creates a new active subscription row

user_entitlement_overrides

Represents a per-user absolute override of base plan limits.

Important fields:
	•	id
	•	user_id
	•	created_by_user_id
	•	revoked_by_user_id
	•	monthly_story_limit
	•	max_pages_per_story
	•	image_quality_mode
	•	voice_clone_limit
	•	monthly_audio_chars_limit
	•	reason
	•	effective_from
	•	effective_to
	•	revoked_at
	•	created_at
	•	updated_at

Usage:
	•	use this when one user needs a different hard cap than the underlying plan row
	•	the latest active override wins for any non-null field it sets

Compliance and trust

consents

Represents explicit user consent for legal or sensitive product actions.

Important fields:
	•	id
	•	user_id
	•	consent_type
	•	accepted_version
	•	accepted_at
	•	ip_address
	•	user_agent

This is especially important for:
	•	voice cloning consent
	•	terms acceptance
	•	privacy acceptance
	•	child content handling

Current implementation note:
	•	the app currently records and checks `terms_of_service`, `privacy_policy`, and `voice_cloning`
	•	accepted versions are date-based strings, currently `2026-03-16`

audit_events

Represents an append-only record of important user/system actions.

Important fields:
	•	id
	•	user_id
	•	actor_user_id
	•	entity_type
	•	entity_id
	•	event_type
	•	event_data_json
	•	created_at

Useful for:
	•	support debugging
	•	compliance needs
	•	deletion tracking
	•	security reviews

Current implementation note:
	•	key event types currently include account registration, consent acceptance, story creation/deletion, voice-profile deletion, voice-sample deletion, voice-clone requests, subscription assignment, plan edits, role changes, and grant/override changes
	•	`actor_user_id` captures which staff/admin user initiated an internal change

usage_credit_grants

Represents additive per-user credits on top of the resolved base limit.

Important fields:
	•	id
	•	user_id
	•	created_by_user_id
	•	revoked_by_user_id
	•	usage_type
	•	quantity
	•	reason
	•	effective_from
	•	effective_to
	•	revoked_at
	•	created_at
	•	updated_at

Usage:
	•	use this for credits like `+2 stories`, `+1 voice clone`, or `+5000 narration chars`
	•	active grants are additive and stack with the resolved plan/override limit

Usage and analytics

usage_records

Represents metered usage and optional cost data.

Important fields:
	•	id
	•	user_id
	•	story_id
	•	story_page_id
	•	usage_type
	•	quantity
	•	unit
	•	provider
	•	provider_cost_micros
	•	created_at

Examples of tracked events:
	•	stories created
	•	images generated
	•	TTS characters synthesized
	•	voice clones created

Current implementation note:
	•	usage is aggregated inside the user’s active subscription period
	•	deletions do not refund usage
	•	`images_generated` is recorded for visibility, but the current plans do not enforce an image quota
	•	effective quota checks resolve in this order: current subscription plan, active entitlement override, then active usage-credit grants

This supports:
	•	analytics
	•	cost accounting
	•	quota enforcement
	•	billing audits

Key relationships

Ownership relationships
	•	one user has many auth_identities
	•	one user has many children
	•	one user has many voice_profiles
	•	one user has many voice_samples
	•	one user has many assets
	•	one user has many stories
	•	one user has many subscriptions
	•	one user has many consents
	•	one user has many audit_events
	•	one user has many usage_records
	•	one user has many user_entitlement_overrides
	•	one user has many usage_credit_grants

Voice relationships
	•	one voice_profile has many voice_samples
	•	one voice_sample references one asset
	•	one voice_profile can narrate many stories

Story relationships
	•	one child has many stories
	•	one story has many story_pages
	•	one story has many story_generation_jobs
	•	one story_page may reference one image asset
	•	one story_page may reference one audio asset
	•	one story may reference one cover asset

Character relationships
	•	one character_profile may belong to one child
	•	one story may include many character_profiles through story_characters

Billing relationships
	•	one plan has many subscriptions
	•	one subscription belongs to one user
	•	one audit_event may belong to one subject user and one actor user

Important modeling choices

User vs auth identity

Keep app ownership separate from login methods.

This avoids polluting the users table with provider-specific login fields and makes OAuth + password coexist naturally.

Voice profile vs voice sample

Keep the final cloned voice separate from the raw training audio.

This makes lifecycle management, cleanup, and provider integration much easier.

Asset metadata vs object bytes

Keep binary files out of Postgres.

This keeps the relational schema small, queryable, and portable.

Story vs page

Pages are the real generation and playback unit.

This supports retries, page-level UX, and richer history of generated content.

Jobs vs story status

Do not try to represent the full async workflow using only stories.status.

Explicit generation job tables make the system easier to operate.

Constraints and indexing recommendations

Suggested constraints:
	•	users.primary_email unique when present
	•	auth_identities(provider, provider_user_id) unique
	•	assets.object_key unique
	•	story_pages(story_id, page_number) unique
	•	story_characters(story_id, character_profile_id) unique

Suggested indexes:
	•	stories(user_id, child_id, status)
	•	story_pages(story_id, page_number)
	•	voice_profiles(user_id, status)
	•	assets(user_id, asset_type)
	•	usage_records(user_id, usage_type, created_at)
	•	audit_events(entity_type, entity_id)

What is intentionally not included yet

The schema does not yet model:
	•	collaborative family accounts
	•	story comments or annotations
	•	public sharing permissions beyond simple link strategies
	•	advanced moderation review workflows
	•	multiple parent ownership models

These can be added later without changing the core domain model.

Summary

The schema is built around this backbone:

User -> Child -> Story -> StoryPage

Around that backbone sit supporting systems for:
	•	auth
	•	voice cloning
	•	file storage
	•	generation jobs
	•	character continuity
	•	billing
	•	consent and auditing

This model is intended to be production-friendly, privacy-aware, and flexible enough for AI-heavy story generation workflows.
