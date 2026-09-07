#!/usr/bin/env python3
"""GCP Connectivity & Vertex AI / GCS Smoke Test for CueCheck.

Verifies:
1. Environment configuration (project, location, bucket, models).
2. Vertex AI Gemini connectivity via google-genai.
3. GCS read/write/delete round-trip.
"""

import os
import sys
import tempfile
import time
from pathlib import Path


def load_env_file(filepath: Path) -> None:
    """Simple .env file loader without extra dependencies."""
    if not filepath.exists():
        return
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip("'\"")
                if key and key not in os.environ:
                    os.environ[key] = val


def handle_service_account_json() -> None:
    """Handle raw JSON service account credentials if passed via env var."""
    sa_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if sa_json and not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        # Write to temporary file for Google Cloud client libraries
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        tmp.write(sa_json)
        tmp.flush()
        tmp.close()
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = tmp.name
        print(f"[config] Wrote GOOGLE_SERVICE_ACCOUNT_JSON to temp file: {tmp.name}")


def check_env_vars() -> dict:
    """Validate required environment variables."""
    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
    bucket = os.environ.get("GCS_BUCKET")
    flash_model = os.environ.get("GEMINI_FLASH_MODEL", "gemini-2.5-flash")
    creds = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")

    status = {
        "GOOGLE_CLOUD_PROJECT": project,
        "GOOGLE_CLOUD_LOCATION": location,
        "GCS_BUCKET": bucket,
        "GEMINI_FLASH_MODEL": flash_model,
        "GOOGLE_APPLICATION_CREDENTIALS": creds,
    }

    missing = []
    if not project or project == "your-gcp-project-id":
        missing.append("GOOGLE_CLOUD_PROJECT")
    if not bucket or bucket == "your-cuecheck-media-bucket":
        missing.append("GCS_BUCKET")

    return {"status": status, "missing": missing}


def test_gemini(project: str, location: str, model_id: str) -> bool:
    """Test one Gemini model call on Vertex AI using google-genai."""
    print(f"\n--- Testing Vertex AI Gemini ({model_id}) ---")
    start_time = time.time()
    try:
        from google import genai

        # Using Vertex AI backend as required by brief Section 2 & 14
        client = genai.Client(
            vertexai=True,
            project=project,
            location=location,
        )

        print(f"[gemini] Calling {model_id} with prompt 'PING'...")
        response = client.models.generate_content(
            model=model_id,
            contents="Respond with only the single word: PONG",
        )
        duration = time.time() - start_time
        reply_text = response.text.strip() if response.text else "<empty>"
        print(f"[gemini] Response received in {duration:.2f}s: '{reply_text}'")
        print("[gemini] PASSED ✓")
        return True
    except Exception as e:
        duration = time.time() - start_time
        print(f"[gemini] FAILED after {duration:.2f}s: {e}", file=sys.stderr)
        return False


def test_gcs(project: str, bucket_name: str) -> bool:
    """Test GCS round-trip: write probe, read probe, delete probe."""
    print(f"\n--- Testing Google Cloud Storage ({bucket_name}) ---")
    start_time = time.time()
    try:
        from google.cloud import storage

        client = storage.Client(project=project)
        bucket = client.bucket(bucket_name)

        probe_blob_name = f"cuecheck_probe_{int(time.time())}.txt"
        probe_content = f"cuecheck-probe-test-{time.time()}"
        blob = bucket.blob(probe_blob_name)

        print(f"[gcs] Uploading probe blob: {probe_blob_name}...")
        blob.upload_from_string(probe_content, content_type="text/plain")

        print(f"[gcs] Reading probe blob: {probe_blob_name}...")
        downloaded = blob.download_as_text()
        assert downloaded == probe_content, "Downloaded probe text does not match uploaded text!"

        print(f"[gcs] Deleting probe blob: {probe_blob_name}...")
        blob.delete()

        duration = time.time() - start_time
        print(f"[gcs] Round-trip succeeded in {duration:.2f}s")
        print("[gcs] PASSED ✓")
        return True
    except Exception as e:
        duration = time.time() - start_time
        print(f"[gcs] FAILED after {duration:.2f}s: {e}", file=sys.stderr)
        return False


def main() -> int:
    env_path = Path(__file__).resolve().parent.parent / ".env"
    load_env_file(env_path)
    handle_service_account_json()

    print("=== CueCheck GCP Smoke Test ===")
    info = check_env_vars()

    for k, v in info["status"].items():
        masked_v = v if k != "GOOGLE_APPLICATION_CREDENTIALS" else (v and Path(v).name)
        print(f"  {k}: {masked_v or '<NOT SET>'}")

    if info["missing"]:
        missing_str = ", ".join(info["missing"])
        print(f"\n[warning] Required environment variables not configured: {missing_str}")
        print("Please copy .env.example to .env and configure your GCP Project and GCS Bucket.")
        print("Offline/mock mode can still be used for development and local testing.")
        return 2

    project = info["status"]["GOOGLE_CLOUD_PROJECT"]
    location = info["status"]["GOOGLE_CLOUD_LOCATION"]
    bucket = info["status"]["GCS_BUCKET"]
    model_id = info["status"]["GEMINI_FLASH_MODEL"]

    gemini_ok = test_gemini(project, location, model_id)
    gcs_ok = test_gcs(project, bucket)

    if gemini_ok and gcs_ok:
        print("\n=== All GCP Smoke Tests PASSED ✓ ===")
        return 0
    else:
        print("\n=== One or more GCP Smoke Tests FAILED ✗ ===", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
