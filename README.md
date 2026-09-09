# FrameKind

**A better cut. For every audience.**

FrameKind helps film editors find missing sound captions, rushed dialogue and timing errors before delivery. Review each finding against the picture, approve a suggested repair and export SRT, WebVTT or a review report. Editors keep the final decision.

## Try it locally

Requires Python 3.11 or 3.12, Node 20+ and FFmpeg/FFprobe. Replit deploys with Python 3.11; the supported range is bounded so its universal dependency resolver does not target untested future Python versions.

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
npm ci --prefix web
npm run build --prefix web
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

Open http://localhost:8000. Click **Step into a sample review**. The built-in sample works without cloud credentials. Its transcript, sound events and visual observations are authored test fixtures, not evidence of a live Gemini call. Custom caption-only runs check timed text and mark untested media dimensions as not checked.

## Live Google Cloud analysis

Copy `.env.example` to `.env`. For the configured deployment, use `GOOGLE_SERVICE_ACCOUNT_JSON`, `GOOGLE_CLOUD_PROJECT` and `GOOGLE_CLOUD_LOCATION=global`. Alternatively, set `VERTEX_API_KEY` where Vertex authorization keys are supported. Short local video uploads can be analyzed inline without a storage bucket. For larger media, configure Application Default Credentials and `GCS_BUCKET` for signed Cloud Storage uploads. Keep credentials on the server.

Gemini transcribes dialogue, listens for non-speech events and examines visual context. An eight-step Google ADK pipeline turns that evidence into deterministic checks and repair proposals. A failed live call remains a failed live call.

The configurable thresholds are project review settings. FrameKind does not certify broadcast, legal or accessibility compliance. Model observations and transcript accuracy need an editor's review.

## Deployment

Import this repository into Replit. Build with `bash scripts/replit_build.sh`; start with `bash scripts/replit_start.sh`. The server binds to `0.0.0.0:$PORT` and serves the compiled React app. Configure secrets in Replit, then publish the app. Attach Postgres for persistent history on deployments with ephemeral storage.

See [deployment notes](docs/TOOLING.md), [architecture](docs/ARCHITECTURE.md) and [recording script](docs/DEMO_SCRIPT.md).

## Repository

| Path | Purpose |
|---|---|
| `engine/` | Timed-text parsing, checks, alignment, repairs and exports |
| `agents/` | Google ADK orchestration and Vertex Gemini calls |
| `api/` | FastAPI, progress events, session-owned runs and SQLAlchemy storage |
| `web/` | React review workspace |
| `profiles/` | Editable review thresholds |
| `samples/` | Demo captions and media |
| `tests/` | Engine, API, persistence and export regression checks |

```bash
pytest -q
ruff check api agents engine scripts tests
npm run build --prefix web
```

## Development record

The initial implementation was created with Google Antigravity, as reported by the author. Codex assisted with the FrameKind rename, interface redesign, security fixes, export fixes, testing and deployment preparation. See [tooling record](docs/TOOLING.md) for evidence and the current Replit Agent status. Runtime AI uses Google models.

## License

Apache-2.0. See [LICENSE](LICENSE).
