[Home](Home) | [Product Tour](Product-Tour) | [Technical Approach](Technical-Approach)

# Privacy and Trust

Privacy is not an extra layer added after generation works. It is part of the product model. Vocaleaf handles child-centered content, parent voice recordings, and generated media, so the storage and access model is deliberately private by default.

## Private by default

The system does not treat media like public static content. Voice samples, generated illustrations, and narration audio are stored in private object storage and accessed through authenticated backend checks plus short-lived signed URLs.

## What lives where

| Data type | Storage approach |
| --- | --- |
| App state and metadata | PostgreSQL |
| Raw voice sample bytes | Private object storage |
| Generated image bytes | Private object storage |
| Generated narration bytes | Private object storage |

This separation keeps large files out of the relational database while preserving precise metadata, ownership rules, and generation state.

## Sensitivity tiers

### Raw voice samples

Raw voice uploads are the most sensitive asset type in the product. They are used to create a narration voice profile, but they are not meant to be broadly exposed, and the normal product UI does not center on playing them back publicly or casually sharing them.

### Generated story media

Story illustrations and narration are also private assets. They may be less sensitive than raw voice recordings, but they are still tied to a family's personalized content and should remain behind application-level authorization.

## Consent matters

Voice cloning is gated by explicit consent during voice profile creation. The product treats cloned narration as a deliberate user action, not a background surprise. A voice profile is only usable for story narration once cloning has completed successfully.

## Why signed access is important

Signed URLs keep the app in control of authorization. The backend verifies ownership first, then grants narrow, temporary access to the exact media object needed. That makes private playback practical without exposing whole buckets or permanent public links.

## Trust through product shape

The UX reflects these rules directly:

- voice profile setup includes consent confirmation
- sample uploads are collected into a dedicated voice workflow
- stories and assets belong to authenticated user accounts
- long-running generation happens in background workers instead of opaque browser-only flows

Vocaleaf is still in active development, but its privacy posture is already built into the architecture rather than deferred to a later cleanup pass.
