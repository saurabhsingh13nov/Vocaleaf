"""Cloudflare R2 helpers for presigned URLs and object metadata."""

from dataclasses import dataclass
from functools import lru_cache

from app.core.config import settings


class R2Error(Exception):
    """Base storage integration error."""


class R2ObjectNotFoundError(R2Error):
    """Raised when the requested object is not present in storage."""


@dataclass(frozen=True)
class R2ObjectMetadata:
    file_size_bytes: int | None
    checksum: str | None


class R2StorageClient:
    """Thin wrapper around an S3-compatible client configured for R2."""

    def __init__(
        self,
        *,
        endpoint_url: str,
        access_key_id: str,
        secret_access_key: str,
        bucket_name: str,
        region: str,
    ) -> None:
        self.endpoint_url = endpoint_url
        self.access_key_id = access_key_id
        self.secret_access_key = secret_access_key
        self.bucket_name = bucket_name
        self.region = region
        self._client = None

    def _get_client(self):
        if self._client is None:
            if not all(
                [
                    self.endpoint_url,
                    self.access_key_id,
                    self.secret_access_key,
                    self.bucket_name,
                ]
            ):
                raise R2Error("R2 storage is not configured")

            try:
                import boto3
            except ModuleNotFoundError as exc:
                raise R2Error("boto3 is required for R2 storage support") from exc

            self._client = boto3.client(
                "s3",
                endpoint_url=self.endpoint_url,
                aws_access_key_id=self.access_key_id,
                aws_secret_access_key=self.secret_access_key,
                region_name=self.region,
            )

        return self._client

    def generate_upload_url(
        self,
        *,
        object_key: str,
        mime_type: str | None,
        expires_in: int,
    ) -> str:
        params = {
            "Bucket": self.bucket_name,
            "Key": object_key,
        }
        if mime_type:
            params["ContentType"] = mime_type

        return self._get_client().generate_presigned_url(
            "put_object",
            Params=params,
            ExpiresIn=expires_in,
            HttpMethod="PUT",
        )

    def generate_download_url(self, *, object_key: str, expires_in: int) -> str:
        return self._get_client().generate_presigned_url(
            "get_object",
            Params={
                "Bucket": self.bucket_name,
                "Key": object_key,
            },
            ExpiresIn=expires_in,
            HttpMethod="GET",
        )

    def delete_object(self, *, object_key: str) -> None:
        try:
            self._get_client().delete_object(
                Bucket=self.bucket_name,
                Key=object_key,
            )
        except Exception as exc:  # pragma: no cover - exercised via mocks in tests
            error_code = None
            response = getattr(exc, "response", None)
            if isinstance(response, dict):
                error_code = response.get("Error", {}).get("Code")
            if error_code in {"404", "NoSuchKey", "NotFound"}:
                raise R2ObjectNotFoundError("Object not found in R2") from exc
            raise R2Error("Failed to delete object from R2") from exc

    def head_object(self, *, object_key: str) -> R2ObjectMetadata:
        try:
            response = self._get_client().head_object(
                Bucket=self.bucket_name,
                Key=object_key,
            )
        except Exception as exc:  # pragma: no cover - exercised via mocks in tests
            error_code = None
            response = getattr(exc, "response", None)
            if isinstance(response, dict):
                error_code = response.get("Error", {}).get("Code")
            if error_code in {"404", "NoSuchKey", "NotFound"}:
                raise R2ObjectNotFoundError("Object not found in R2") from exc
            raise R2Error("Failed to retrieve object metadata from R2") from exc

        etag = response.get("ETag")
        checksum = etag.strip('"') if isinstance(etag, str) else None
        return R2ObjectMetadata(
            file_size_bytes=response.get("ContentLength"),
            checksum=checksum,
        )


@lru_cache
def get_r2_client() -> R2StorageClient:
    return R2StorageClient(
        endpoint_url=settings.r2_endpoint_url,
        access_key_id=settings.r2_access_key_id,
        secret_access_key=settings.r2_secret_access_key,
        bucket_name=settings.r2_bucket_name,
        region=settings.r2_region,
    )
