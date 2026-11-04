"""Google Cloud Storage utilities for CueCheck.

Handles:
- Parsing gs:// URIs
- Signed URL generation for secure browser uploads
- Upload / download helpers for video and timed-text deliverables
"""

import os
from datetime import timedelta
from typing import Optional, Tuple
from urllib.parse import urlparse


def parse_gs_uri(uri: str) -> Tuple[str, str]:
    """Parse gs://bucket_name/blob_path into (bucket_name, blob_path)."""
    parsed = urlparse(uri)
    if parsed.scheme != "gs":
        raise ValueError(f"Invalid GCS URI (must start with gs://): {uri}")
    bucket_name = parsed.netloc
    blob_path = parsed.path.lstrip("/")
    return bucket_name, blob_path


def get_gcs_client(project: Optional[str] = None):
    """Obtain an authenticated storage.Client instance."""
    from google.cloud import storage

    proj = project or os.environ.get("GOOGLE_CLOUD_PROJECT")
    return storage.Client(project=proj)


def generate_signed_upload_url(
    bucket_name: str,
    blob_name: str,
    content_type: str = "application/octet-stream",
    ttl_seconds: int = 900,
    project: Optional[str] = None,
) -> str:
    """Generate a v4 signed PUT URL allowing direct browser upload to GCS."""
    client = get_gcs_client(project)
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)

    signed_url = blob.generate_signed_url(
        version="v4",
        expiration=timedelta(seconds=ttl_seconds),
        method="PUT",
        content_type=content_type,
    )
    return signed_url


def generate_signed_download_url(
    bucket_name: str,
    blob_name: str,
    ttl_seconds: int = 900,
    project: Optional[str] = None,
) -> str:
    """Generate a v4 signed GET URL for downloading an asset."""
    client = get_gcs_client(project)
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)

    signed_url = blob.generate_signed_url(
        version="v4",
        expiration=timedelta(seconds=ttl_seconds),
        method="GET",
    )
    return signed_url


def download_blob_to_string(gs_uri: str, project: Optional[str] = None) -> str:
    """Download text content from a gs:// URI."""
    bucket_name, blob_path = parse_gs_uri(gs_uri)
    client = get_gcs_client(project)
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_path)
    return blob.download_as_text()


def upload_string_to_blob(
    content: str, gs_uri: str, content_type: str = "text/plain", project: Optional[str] = None
) -> None:
    """Upload text content directly to a gs:// URI."""
    bucket_name, blob_path = parse_gs_uri(gs_uri)
    client = get_gcs_client(project)
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_path)
    blob.upload_from_string(content, content_type=content_type)
