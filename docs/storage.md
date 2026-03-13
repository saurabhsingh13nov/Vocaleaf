Storage

This document describes the storage model for the storybook app.

It covers:
	•	what is stored in Postgres vs object storage
	•	how assets are modeled
	•	private file access patterns
	•	signed URL behavior
	•	storage layout recommendations
	•	retention and cleanup guidance
	•	security expectations for voice samples and story media

Goals

The storage system should support:
	•	private uploads of raw parent voice samples
	•	private storage of generated story images
	•	private storage of generated narration audio
	•	efficient browser playback and image loading
	•	clear metadata tracking in the database
	•	secure temporary access to stored objects
	•	future portability across S3-compatible providers

Core design principle

Use two layers:
	•	PostgreSQL for metadata
	•	object storage for file bytes

Do not store raw binary files in Postgres.

What belongs where

PostgreSQL stores

Postgres should store metadata such as:
	•	asset ownership
	•	storage provider
	•	bucket name
	•	object key
	•	upload status
	•	MIME type
	•	file size
	•	width/height for images
	•	duration for audio
	•	confirmed_at timestamp
	•	privacy flags
	•	deletion timestamps
	•	relationships to stories, pages, and voice samples

Object storage stores

Object storage should store the actual bytes for:
	•	raw voice sample uploads
	•	generated narration audio
	•	generated page illustrations
	•	cover images
	•	thumbnails or alternate sizes
	•	any future derived media assets

Why object storage is the right choice

Object storage is the correct place for media because it is built for:
	•	large file storage
	•	cheap scale
	•	direct browser delivery
	•	lifecycle rules
	•	content metadata
	•	signed URL workflows

It also keeps the relational database smaller and easier to manage.

Recommended providers

Good options for this project:
	•	Amazon S3
	•	Cloudflare R2
	•	Supabase Storage
	•	other S3-compatible storage systems

Recommendation

For the most standard production setup:
	•	S3 is the safest default

For lower bandwidth/egress cost sensitivity:
	•	R2 is attractive if the traffic model fits

Choose one provider abstraction and keep provider-specific code inside a storage service.

Asset model

Use a generic assets table in Postgres.

This table stores metadata for all file-like resources.

Typical asset categories

Examples of asset_type:
	•	image
	•	audio
	•	voice_sample
	•	cover_image
	•	thumbnail

Why a generic assets table is preferred

Do not create separate file tables like:
	•	story_images
	•	story_audio
	•	voice_files
	•	cover_files

A generic asset table is simpler because:
	•	one model works for all file categories
	•	the same storage/access logic is reusable
	•	new asset categories can be added without schema sprawl

How assets relate to domain objects

Voice system
	•	voice_samples.asset_id points to the uploaded raw audio file

Story system
	•	stories.cover_asset_id points to an optional cover image
	•	story_pages.image_asset_id points to the page illustration
	•	story_pages.audio_asset_id points to the page narration audio

This keeps file storage concerns separate from product-domain tables.

Private-by-default rule

All buckets and objects should be treated as private by default.

This is especially important because the product contains:
	•	children’s personalized story content
	•	cloned parent voice audio
	•	raw uploaded parent voice samples

Do not rely on public bucket access for application behavior.

Signed URL model

The recommended access model is:
	•	backend checks auth and ownership
	•	backend generates a short-lived signed URL
	•	browser accesses object storage directly using that URL

Important security property

A signed URL is a temporary bearer credential.

This means:
	•	anyone holding the signed URL can use it until it expires
	•	signed URLs are not magically limited to the currently logged-in user
	•	authorization happens before issuing the signed URL

Implication

The backend must never generate signed URLs without:
	•	authenticating the caller
	•	checking ownership or access rights
	•	scoping the URL to the exact object needed
	•	using a short expiration time

Upload flow

Recommended flow for uploads such as voice samples:
	1.	authenticated frontend requests an upload URL from FastAPI
	2.	FastAPI validates the user, creates an assets row in pending state, and creates an object key
	3.	FastAPI returns a short-lived signed upload URL and the asset_id
	4.	browser uploads directly to object storage
	5.	frontend notifies backend that upload completed
	6.	backend confirms the object exists, marks the asset ready, and then creates related domain rows if needed

Recommended asset lifecycle fields:
	•	upload_status = pending until confirm succeeds
	•	upload_status = ready after the backend verifies the object exists
	•	confirmed_at records when the backend accepted the upload

Why direct-to-storage upload is better

It avoids sending large files through the API server and improves:
	•	scalability
	•	latency
	•	backend resource usage

Download/read flow

Recommended flow for reading private images/audio:
	1.	frontend requests page asset access from FastAPI
	2.	FastAPI checks user identity and ownership of the story
	3.	FastAPI returns short-lived signed read URLs
	4.	browser loads the image/audio directly from object storage

This is the preferred default for generated story media.

When to use a backend proxy instead

A backend proxy is more restrictive but more expensive.

Use proxying if you need:
	•	stricter access control for highly sensitive files
	•	detailed read logging through the app server
	•	complete hiding of storage paths/keys
	•	content transformation on the fly

For this project, proxying is most justified for:
	•	the most sensitive raw voice sample workflows
	•	special admin/compliance access paths

For normal story playback, signed read URLs are usually the best choice.

Sensitivity tiers

It helps to treat stored files in tiers.

Tier 1: raw voice samples

Most sensitive.

Recommended handling:
	•	private bucket or private prefix
	•	short-lived signed upload URLs only
	•	no routine direct read access in the product UI
	•	no generic signed read URL from the shared asset endpoint
	•	backend-only access where possible
	•	aggressive cleanup/retention policy

Tier 2: generated narration audio

Sensitive.

Recommended handling:
	•	private bucket
	•	signed read URLs with short expiry
	•	tied to strict ownership checks

Tier 3: generated story images

Still private by default.

Recommended handling:
	•	private bucket
	•	signed read URLs for normal app playback
	•	optional cached derived versions if product rules permit

Suggested storage layout

Use a predictable object key structure.

Example layout:

voice-samples/{user_id}/{voice_profile_id-or-temp}/{uuid}.wav
stories/{user_id}/{story_id}/cover/{uuid}.webp
stories/{user_id}/{story_id}/pages/{page_number}/image/{uuid}.webp
stories/{user_id}/{story_id}/pages/{page_number}/audio/{uuid}.mp3
derived/{user_id}/{story_id}/pages/{page_number}/thumbnail/{uuid}.webp

Key design rules
	•	include user_id for ownership partitioning
	•	include story_id for story-level grouping
	•	avoid exposing meaningful secrets in object keys
	•	use generated IDs rather than user-provided filenames
	•	keep the layout stable for easier debugging and cleanup

Raw vs derived assets

It is useful to distinguish between:
	•	raw assets: original uploaded/generated media
	•	derived assets: thumbnails, compressed versions, alternate encodings

This distinction can exist through:
	•	asset_type
	•	naming conventions
	•	metadata fields added later if needed

Do not overwrite raw files with transformed versions unless there is a very deliberate reason.

Metadata to track in assets

Recommended fields include:
	•	id
	•	user_id
	•	storage_provider
	•	bucket_name
	•	object_key
	•	asset_type
	•	mime_type
	•	file_size_bytes
	•	checksum
	•	width
	•	height
	•	duration_ms
	•	is_private
	•	created_at
	•	deleted_at

These fields allow you to:
	•	locate the object
	•	verify ownership
	•	serve the file correctly
	•	compute analytics and cleanup
	•	support provider migration later

Signed URL expiration guidance

Use short expirations.

Recommended defaults
	•	signed upload URL: around 5 minutes
	•	signed read URL for story playback: around 5 to 15 minutes

The exact values can be tuned, but long-lived signed URLs should be avoided.

Do not store signed URLs in the database

Store only:
	•	storage provider
	•	bucket name
	•	object key
	•	metadata

Generate signed URLs on demand.

Signed URLs are temporary credentials, not durable object references.

Deletion and retention

The product should support both logical deletion and actual storage cleanup.

Recommended pattern
	•	soft-delete metadata first when appropriate
	•	queue cleanup jobs for storage deletion
	•	separate user-facing deletion from storage lifecycle tasks

Voice sample retention

Raw voice samples are the most sensitive stored media.

Recommended approach:
	•	keep only what is operationally necessary
	•	delete unused or obsolete raw samples quickly
	•	define a clear retention rule early
	•	make the retention policy explicit in docs and privacy notices

Generated story media retention

Generated images/audio can usually be kept longer, but should still support:
	•	user deletion requests
	•	story deletion cleanup
	•	legal/compliance deletion workflows

Orphan prevention and cleanup

The system should avoid orphaned files and orphaned DB rows.

Good practice
	•	create storage object keys deterministically during upload/generation
	•	record DB metadata promptly after successful upload/generation
	•	run periodic reconciliation jobs
	•	clean up stale uploads that never completed domain association

Examples of orphans:
	•	a voice sample file uploaded but no voice_samples row created
	•	a generated page image stored but page update failed
	•	an assets row pointing to an object that was manually removed

Security requirements

Buckets
	•	private by default
	•	no public listing
	•	least-privilege credentials for backend and workers

Signed URL issuance
	•	only after auth and ownership checks
	•	short expiration
	•	scoped to exact object/action

Sensitive media
	•	raw voice samples should have the strictest handling
	•	avoid exposing raw voice sample reads through the frontend unless required
	•	log sensitive storage operations where useful

Filenames and metadata
	•	do not trust user-supplied filenames
	•	validate MIME types and file extensions
	•	enforce file size limits
	•	consider media validation/transcoding before provider use

FastAPI responsibilities

The FastAPI backend should handle:
	•	signed upload URL issuance
	•	signed read URL issuance
	•	asset metadata creation
	•	ownership checks
	•	deletion requests
	•	coordination with workers after uploads/generation

The backend should not be the default path for streaming all media bytes to clients.

Worker responsibilities

Workers should:
	•	write generated media to object storage
	•	create or update assets rows
	•	attach assets to domain entities such as story_pages
	•	record metadata like duration or dimensions
	•	cleanup partial outputs on failure where possible

Recommended storage abstractions in code

Suggested modules:
	•	storage/service.py — provider-neutral operations
	•	storage/models.py — asset helpers if needed
	•	storage/providers/s3.py — provider-specific implementation
	•	storage/presign.py — signed URL generation helpers

Keep object storage provider details out of route handlers and domain services.

Example storage flows

Voice sample upload

Frontend -> FastAPI -> signed upload URL
         -> Browser uploads to object storage
         -> FastAPI creates asset + voice_sample
         -> Worker consumes sample for cloning

Story image generation

Worker -> image provider -> generated image
       -> upload/store in object storage
       -> create asset row
       -> attach asset to story_page.image_asset_id

Story playback

Frontend -> FastAPI -> ownership check
         -> FastAPI returns signed image/audio URLs
         -> Browser loads directly from object storage

What is out of scope for now

This document does not yet define:
	•	advanced media transcoding pipelines
	•	DRM-style protections
	•	public asset sharing strategies
	•	cross-region replication
	•	versioned media history beyond current asset references

These can be added later without changing the core storage model.

Summary

The storage architecture is built on one simple rule:

Postgres stores metadata.
Object storage stores bytes.

Everything else follows from that:
	•	generic assets metadata
	•	private buckets
	•	signed URLs for access
	•	short-lived upload and read permissions
	•	stricter handling for raw voice samples
	•	object key layouts that support cleanup and debugging
