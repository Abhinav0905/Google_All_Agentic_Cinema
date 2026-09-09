# FrameKind

**A better cut. For every audience.**

FrameKind helps film editors find missing sound captions, rushed dialogue and timing errors before delivery. Review each finding against the picture, approve a suggested repair and export SRT, WebVTT or a review report. Editors keep the final decision.

**[Open FrameKind](https://google-all-agentic-cinema--abhinav0905.replit.app)** and choose **Step into a sample review** for the authored demonstration.

Revision `c0fc1f3` is deployed with a fix for terminated idle database connections. The sample's approved decision and identical SRT export survived republishing, a fresh browser live review completed all eight steps, and review creation returned HTTP 201 before and after 180.6 seconds of client idle time.

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

The configurable thresholds are project review settings. FrameKind does not certify broadcast, legal or accessibility compliance. Model observations and transcript accuracy need an editor's review. In the hosted test, Gemini Pro described a woman slapping a man, an event absent from the original animation. Treat visual descriptions and the findings derived from them as proposals, not ground truth.

## Deployment

Import this repository into Replit. Build with `bash scripts/replit_build.sh`; start with `bash scripts/replit_start.sh`. The build requires `uv`, installs the checked-in lock into the project `.venv`, then builds React. The start script uses that environment and binds to `0.0.0.0:$PORT`. Configure secrets in Replit and attach Postgres for persistent history on deployments with ephemeral storage. Keep one serving process and one instance.

As of September 9, 2026, revision `c0fc1f3` is publicly deployed on Replit. A fresh browser live review completed all eight steps with 36 findings and 23 proposals. Earlier hosted checks verified an approved repair, identical repeated SRT exports, cross-session denial and HTTP 206 video playback. After republishing, the browser sample retained 19 findings and its approved edit, loaded 60-second video metadata and produced the same 1,189-byte SRT. The current 109 passing tests were run locally, and the production idle-period creation check passed. See the [readiness record](docs/SUBMISSION_READINESS.md) for details.

Replit currently lists October 8, 2026 as the deployment expiry date. Keep the app available through the full judging window; check the exact expiry time and extend availability if needed.

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

The initial implementation was created with Google Antigravity, as reported by the author. Codex assisted with the FrameKind rename, interface redesign, security fixes, export fixes, testing and deployment preparation. Replit Agent checked the imported environment, added a Postgres module and started the build before its free quota stopped the task. Later build troubleshooting and checks were manual. See the [tooling record](docs/TOOLING.md) for attribution. Runtime AI uses Google models; that does not establish eligibility under the contest's development-tool restrictions.

## License

Apache-2.0. See [LICENSE](LICENSE).
