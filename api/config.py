"""Environment and path configuration for the CueCheck API."""

import os
import tempfile
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
SAMPLES_DIR = ROOT_DIR / "samples"
WEB_DIST = ROOT_DIR / "web" / "dist"
DATA_DIR = ROOT_DIR / ".data" / "runs"


def load_env_file(filepath: Path) -> None:
    if not filepath.exists():
        return
    for line in filepath.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        val = val.strip().strip("'\"")
        if key and key not in os.environ:
            os.environ[key] = val


def handle_service_account_json() -> None:
    sa_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if sa_json and not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        tmp.write(sa_json)
        tmp.flush()
        tmp.close()
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = tmp.name


def bootstrap_env() -> None:
    load_env_file(ROOT_DIR / ".env")
    handle_service_account_json()
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def gcp_configured() -> bool:
    if os.environ.get("VERTEX_API_KEY", "").strip():
        return True
    project = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
    return bool(project and project != "your-gcp-project-id")


def gcs_configured() -> bool:
    bucket = os.environ.get("GCS_BUCKET", "")
    project = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
    return bool(
        project
        and project != "your-gcp-project-id"
        and bucket
        and bucket != "your-cuecheck-media-bucket"
    )


def signed_url_ttl() -> int:
    return int(os.environ.get("SIGNED_URL_TTL_SECONDS", "900"))


def gcs_bucket() -> str:
    return os.environ.get("GCS_BUCKET", "")
