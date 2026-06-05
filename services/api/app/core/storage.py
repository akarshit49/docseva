#genai: MinIO / S3-compatible object storage client.
#genai: WS-B (Sprint 1) — tenacity retry around every S3 op.
from __future__ import annotations

import io
import logging
from pathlib import Path

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError, EndpointConnectionError
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import settings

logger = logging.getLogger(__name__)

_TRANSIENT_ERRORS = (EndpointConnectionError, ConnectionError, TimeoutError)
_storage_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=5),
    retry=retry_if_exception_type(_TRANSIENT_ERRORS),
    reraise=True,
    before_sleep=before_sleep_log(logger, logging.WARNING),
)

_BUCKETS = [
    settings.minio_bucket_uploads,
    settings.minio_bucket_outputs,
    settings.minio_bucket_assets,
]


_SCHEME = "https" if settings.minio_use_ssl else "http"
_INTERNAL_ENDPOINT = f"{_SCHEME}://{settings.minio_endpoint}"
#genai: WS-1 fix — presigned URLs must be signed against the host the *client* hits
_PUBLIC_HOST = (settings.minio_public_endpoint or "").strip() or settings.minio_endpoint
_PUBLIC_ENDPOINT = f"{_SCHEME}://{_PUBLIC_HOST}"


def _client():
    return boto3.client(
        "s3",
        endpoint_url=_INTERNAL_ENDPOINT,
        aws_access_key_id=settings.minio_access_key,
        aws_secret_access_key=settings.minio_secret_key,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",  # MinIO ignores this but boto3 requires it
    )


def _public_client():
    return boto3.client(
        "s3",
        endpoint_url=_PUBLIC_ENDPOINT,
        aws_access_key_id=settings.minio_access_key,
        aws_secret_access_key=settings.minio_secret_key,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )


def ensure_buckets() -> None:
    """Create MinIO buckets if they don't exist. Called on API startup."""
    client = _client()
    for bucket in _BUCKETS:
        try:
            client.head_bucket(Bucket=bucket)
        except ClientError as e:
            if e.response["Error"]["Code"] in ("404", "NoSuchBucket"):
                client.create_bucket(Bucket=bucket)


@_storage_retry
def upload_file(bucket: str, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
    """Upload bytes to MinIO. Returns the key."""
    _client().put_object(
        Bucket=bucket,
        Key=key,
        Body=data,
        ContentType=content_type,
    )
    return key


def upload_local_file(bucket: str, key: str, local_path: Path) -> str:
    """Upload a local file. Returns the key."""
    with open(local_path, "rb") as fh:
        return upload_file(bucket, key, fh.read())


@_storage_retry
def download_file(bucket: str, key: str) -> bytes:
    """Download object bytes from MinIO."""
    resp = _client().get_object(Bucket=bucket, Key=key)
    return resp["Body"].read()


@_storage_retry
def presigned_url(bucket: str, key: str, expiry: int | None = None) -> str:
    """Generate a presigned GET URL that public clients can hit directly."""
    return _public_client().generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=expiry or settings.presigned_url_expiry,
    )


def delete_file(bucket: str, key: str) -> None:
    try:
        _client().delete_object(Bucket=bucket, Key=key)
    except ClientError:
        # Already gone; treat as success.
        pass
    except _TRANSIENT_ERRORS as exc:
        # Best-effort cleanup; log and move on rather than blocking the caller.
        logger.warning("delete_file transient error for %s/%s: %s", bucket, key, exc)
