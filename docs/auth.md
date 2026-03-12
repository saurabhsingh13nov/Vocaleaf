Auth

This document describes the authentication and account model for the storybook app.

It covers:
	•	account modeling
	•	email/password login
	•	OAuth login
	•	how users and auth identities relate
	•	password storage requirements
	•	recommended session and token approach
	•	account-linking and duplicate-account handling

Goals

The auth system should support:
	•	email/password signup and login
	•	OAuth login, starting with Google and optionally Apple
	•	linking multiple login methods to one app account
	•	secure password handling
	•	email verification
	•	password reset
	•	backend-friendly auth for FastAPI

Core modeling decision

Authentication must be separated into two layers:
	•	users = the app account
	•	auth_identities = the login methods attached to that account

This is the most important auth design choice in the system.

Why auth is split this way

users

This table represents the person/account in the product.

It owns:
	•	children
	•	stories
	•	voice profiles
	•	subscriptions
	•	assets
	•	consents
	•	usage records

It is the stable product identity.

auth_identities

This table represents how that user signs in.

Examples:
	•	password login
	•	Google OAuth
	•	Apple OAuth

One user can have multiple auth_identities.

This allows:
	•	sign in with password
	•	later add Google
	•	later add Apple
	•	all attached to the same product account

Why not store all auth fields in users

Do not add columns like:
	•	google_sub
	•	apple_sub
	•	password_hash
	•	facebook_id

to the users table directly.

That design becomes messy quickly and makes it harder to support multiple login methods per account.

Keeping login methods in auth_identities is cleaner, more extensible, and easier to reason about.

Tables involved

users

Represents the account itself.

Expected fields:
	•	id
	•	primary_email
	•	full_name
	•	avatar_url
	•	status
	•	email_verified_at
	•	last_login_at
	•	created_at
	•	updated_at

Notes:
	•	primary_email may be nullable temporarily for some onboarding edge cases
	•	email_verified_at refers to the primary account email status
	•	last_login_at reflects the most recent successful login across all auth methods

auth_identities

Represents one login method.

Expected fields:
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
	•	for provider = password, password_hash must be present
	•	for OAuth providers, provider_user_id must be present
	•	password_hash must be null for OAuth-only identities

Supported auth providers

Recommended initial providers:
	•	password
	•	google
	•	apple

You can add others later without changing the users table.

Email/password auth

Signup flow
	1.	user submits email and password
	2.	backend validates the password policy
	3.	backend normalizes the email
	4.	backend checks for an existing account/identity conflict
	5.	backend creates a users row
	6.	backend creates a auth_identities row with provider = password
	7.	backend stores a password hash
	8.	backend creates an email verification record or sends a verification message

Login flow
	1.	user submits email and password
	2.	backend finds the matching auth_identities row for provider = password
	3.	backend verifies the password hash
	4.	backend updates last_login_at
	5.	backend issues a session or token

Password storage requirements

Passwords must never be:
	•	stored in plaintext
	•	encrypted reversibly
	•	logged
	•	sent back to the client

Passwords should be hashed using:
	•	Argon2id preferred
	•	bcrypt acceptable if needed

Salt requirement

Yes, passwords must be salted.

But:
	•	do not store a separate salt column
	•	modern password hashing algorithms already include the salt in the stored hash string

Store only:
	•	password_hash

Do not store:
	•	password
	•	password_salt

OAuth auth

Important fact

OAuth providers such as Google do not send you the user’s password.

For OAuth sign-in, you will not receive:
	•	the user’s password
	•	a password hash
	•	any reusable password credential

What to store instead

For an OAuth identity, store:
	•	provider
	•	provider_user_id
	•	provider-supplied email if available
	•	verification state
	•	optional profile fields if needed

For OAuth identities:
	•	password_hash = NULL

Why provider_user_id matters

Do not use email as the only stable identity key for OAuth.

Instead, use the provider’s stable user identifier:
	•	Google sub
	•	Apple subject identifier

Emails can change. Provider subject IDs are the safer long-term identity key.

Google OAuth flow
	1.	frontend completes Google sign-in
	2.	backend receives an authorization code or verified token payload
	3.	backend validates the token with Google or through the OAuth library flow
	4.	backend extracts:
	•	provider user ID (sub)
	•	email
	•	name/avatar if needed
	5.	backend looks up auth_identities by (provider, provider_user_id)
	6.	if found, log the user in
	7.	if not found, decide whether to:
	•	create a new account, or
	•	link to an existing account

Linking multiple identities to one user

A user may have multiple auth_identities.

Example:
	•	one password identity
	•	one Google identity
	•	one Apple identity

All should point to the same users.id if they belong to the same person/account.

Common linking cases

Case 1: user signs up with password first, adds Google later
	•	existing users row remains
	•	add a second auth_identities row for Google

Case 2: user signs up with Google first, later sets a password
	•	existing users row remains
	•	add a password identity

Case 3: user signs in with Google and the email matches an existing password account
This must be handled carefully.

Recommended approach:
	•	do not silently merge accounts purely on email in every case
	•	prefer explicit linking after proving control of the existing account
	•	if you do auto-link, document the exact trust assumptions clearly

Recommended account-linking policy

Start with a conservative rule set.

Safe default
	•	treat (provider, provider_user_id) as the primary OAuth identity key
	•	treat email as a useful hint, not the only identity key
	•	require explicit user confirmation before linking identities across existing accounts in ambiguous situations

Suggested linking behavior

Password signup, then Google login with same email
Recommended:
	•	ask the user to sign into the existing account first
	•	then link Google from inside account settings

Google signup first, then password set later
Recommended:
	•	allow the logged-in user to add a password from account settings

This reduces duplicate-account mistakes and accidental merges.

Sessions and tokens

Recommended v1 approach

Use server-backed auth with one of these patterns:
	•	secure HTTP-only cookie session
	•	short-lived access token + refresh mechanism

For a web app with FastAPI and a browser frontend, the simplest robust option is often:
	•	HTTP-only secure cookies
	•	backend-managed session issuance

Why cookies are a good default
	•	safer against some client-side token leakage patterns
	•	simpler for same-site web flows
	•	works well for browser-based login/logout

If using JWT

If you use JWTs, keep the design disciplined:
	•	short-lived access tokens
	•	refresh token rotation
	•	secure storage approach
	•	revocation strategy documented

Do not choose JWT just because it seems modern. For your app, cookie-backed sessions are a strong default.

Email verification

Email verification should exist even if OAuth is supported.

For password signup

Recommended:
	•	create the account
	•	issue verification token
	•	verify email before enabling all sensitive actions, or before first full use

For OAuth identities

You may mark the identity as verified if the provider is trusted and the email claim is verified.

Still keep your own fields:
	•	auth_identities.is_verified
	•	users.email_verified_at

Document how these are synchronized.

Password reset

Password reset should be separate from auth_identities and users.

Recommended supporting table later:
	•	password_reset_tokens

Suggested fields:
	•	id
	•	user_id or auth_identity_id
	•	token_hash
	•	expires_at
	•	used_at
	•	created_at

Never store raw reset tokens in the database.
Store only a hashed form.

Supporting auth tables to add soon

These are not part of the minimal account model, but should be added early:
	•	email_verification_tokens
	•	password_reset_tokens
	•	user_sessions

email_verification_tokens

Used for verifying password-based email ownership.

password_reset_tokens

Used for secure password reset flows.

user_sessions

Useful if you want:
	•	session revocation
	•	multi-device session visibility
	•	auditability
	•	logout-all-devices support

Security requirements

Passwords
	•	use Argon2id
	•	never store plaintext passwords
	•	never log passwords
	•	no separate salt column
	•	enforce password policy at the API layer

OAuth
	•	validate tokens correctly
	•	verify issuer/audience/expiry according to provider rules
	•	trust provider subject IDs more than email alone
	•	do not skip verification steps for convenience

Sessions
	•	use secure cookies in production
	•	use HTTP-only cookies
	•	set SameSite appropriately
	•	rotate or expire sessions properly

Rate limiting and abuse prevention

Add rate limits around:
	•	login attempts
	•	signup
	•	password reset requests
	•	email verification resend

Recommended FastAPI auth shape

Suggested internal modules:
	•	auth/service.py — account creation, login, linking, password verify
	•	auth/oauth.py — OAuth provider adapters
	•	auth/passwords.py — password hashing and verification helpers
	•	auth/sessions.py — session issue/verify/revoke
	•	auth/dependencies.py — get_current_user, auth guards

Example auth states

Password user
	•	users row exists
	•	one auth_identities row with:
	•	provider = password
	•	password_hash present

Google-only user
	•	users row exists
	•	one auth_identities row with:
	•	provider = google
	•	provider_user_id present
	•	password_hash = NULL

User with both password and Google
	•	one users row
	•	two auth_identities rows

Recommended constraints

At the database level:
	•	users.primary_email unique when present
	•	auth_identities(provider, provider_user_id) unique
	•	require password_hash for password identities
	•	require provider_user_id for OAuth identities

At the application level:
	•	normalize emails consistently
	•	prevent unsafe account auto-merges
	•	prevent duplicate identity creation for the same provider subject

What is out of scope for now

This document does not yet define:
	•	full MFA design
	•	WebAuthn/passkeys
	•	phone login
	•	enterprise SSO
	•	organization/team account auth

These can be added later without changing the core users + auth_identities model.

Summary

The auth system is built on one simple principle:

User = account owner
AuthIdentity = sign-in method

That allows the app to support:
	•	email/password
	•	Google/Apple OAuth
	•	multiple identities per account
	•	safe long-term extensibility

The key security rules are:
	•	use Argon2id for password hashing
	•	store no separate salt column
	•	OAuth identities do not have password hashes
	•	use provider subject IDs as the stable OAuth identity key