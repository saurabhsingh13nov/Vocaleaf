"""All domain enums for the Vocaleaf schema.

PostgreSQL native ENUMs — type safety at the DB level.
"""

import enum


class UserStatus(str, enum.Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETED = "deleted"


class AuthProvider(str, enum.Enum):
    PASSWORD = "password"
    GOOGLE = "google"
    APPLE = "apple"


class VoiceProfileStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"
    DELETED = "deleted"


class VoiceSampleStatus(str, enum.Enum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class StoryStatus(str, enum.Enum):
    DRAFT = "draft"
    GENERATING = "generating"
    READY = "ready"
    FAILED = "failed"
    DELETED = "deleted"


class StoryPageStatus(str, enum.Enum):
    PENDING = "pending"
    TEXT_READY = "text_ready"
    IMAGE_READY = "image_ready"
    AUDIO_READY = "audio_ready"
    COMPLETE = "complete"
    FAILED = "failed"


class AssetType(str, enum.Enum):
    PAGE_IMAGE = "page_image"
    PAGE_AUDIO = "page_audio"
    VOICE_SAMPLE = "voice_sample"
    COVER_IMAGE = "cover_image"
    THUMBNAIL = "thumbnail"


class JobStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class GenerationType(str, enum.Enum):
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"


class SubscriptionStatus(str, enum.Enum):
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class ConsentType(str, enum.Enum):
    TERMS_OF_SERVICE = "terms_of_service"
    PRIVACY_POLICY = "privacy_policy"
    VOICE_CLONING = "voice_cloning"
    CHILD_DATA = "child_data"
