#genai: MinIO client for the bot — upload/download files, presigned URLs.
from __future__ import annotations

import logging
from pathlib import Path

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from app.config import settings

logger = logging.getLogger(__name__)

_SCHEME = "https" if settings.minio_use_ssl else "http"
_ENDPOINT = f"{_SCHEME}://{settings.minio_endpoint}"

# Public endpoint for presigned URLs — must be reachable by the end user's device.
# Presigned URL signatures are tied to the exact hostname used when creating the client,
# so we need a separate client that signs with the public host.
_PUBLIC_HOST = settings.minio_public_endpoint.strip() or settings.minio_endpoint
_PUBLIC_ENDPOINT = f"{_SCHEME}://{_PUBLIC_HOST}"


def _client():
    """Internal client — used for uploads, downloads, and object operations."""
    return boto3.client(
        "s3",
        endpoint_url=_ENDPOINT,
        aws_access_key_id=settings.minio_access_key,
        aws_secret_access_key=settings.minio_secret_key,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )


def _public_client():
    #genai: Separate client whose presigned URLs embed the public hostname in the signature.
    # Using _client() then replacing the host string breaks the HMAC signature.
    return boto3.client(
        "s3",
        endpoint_url=_PUBLIC_ENDPOINT,
        aws_access_key_id=settings.minio_access_key,
        aws_secret_access_key=settings.minio_secret_key,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )


#genai: WS-1 — updated signature with doc_id for unique keys
def upload_output(org_id: str, doc_id: str, local_path: Path) -> str:
    """Upload processed output file. Returns the MinIO key."""
    key = f"outputs/{org_id}/{doc_id}/{local_path.name}"
    with open(local_path, "rb") as fh:
        _client().put_object(
            Bucket=settings.minio_bucket_outputs,
            Key=key,
            Body=fh.read(),
        )
    return key


#genai: WS-1 — new function to store uploaded input files
def upload_input(org_id: str, doc_id: str, local_path: Path) -> str:
    """Upload user's input file for durability. Returns the MinIO key."""
    key = f"uploads/{org_id}/{doc_id}/{local_path.name}"
    with open(local_path, "rb") as fh:
        _client().put_object(
            Bucket=settings.minio_bucket_uploads,
            Key=key,
            Body=fh.read(),
        )
    return key


#genai: WS-1 — presigned URL for re-download from /history
def generate_presigned_url(bucket: str, key: str, expiry: int | None = None) -> str | None:
    """
    Generate a presigned download URL reachable by the end user's device.

    Uses _public_client() so the HMAC signature is computed against the public
    hostname — the URL is valid as-is and does not need any post-hoc rewriting.
    """
    try:
        return _public_client().generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=expiry or settings.presigned_url_expiry,
        )
    except ClientError:
        logger.warning("Failed to generate presigned URL for %s/%s", bucket, key, exc_info=True)
        return None


#genai: WS-1 — delete expired objects
def delete_object(bucket: str, key: str) -> None:
    """Delete a single object from MinIO."""
    _client().delete_object(Bucket=bucket, Key=key)


def download_asset(key: str, dest: Path) -> Path:
    """Download an asset (e.g. company logo) from MinIO to a local path."""
    data = _client().get_object(Bucket=settings.minio_bucket_assets, Key=key)["Body"].read()
    dest.write_bytes(data)
    return dest


def download_format_template(file_key: str, dest: Path) -> Path:
    """Download a sister-quotation format template from MinIO assets bucket."""
    data = _client().get_object(Bucket=settings.minio_bucket_assets, Key=file_key)["Body"].read()
    dest.write_bytes(data)
    return dest
