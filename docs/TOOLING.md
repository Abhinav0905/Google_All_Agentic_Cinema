# FrameKind tooling and deployment record

## Development attribution

| Tool | Work | Evidence status |
|---|---|---|
| Google Antigravity | Initial engine, ADK pipeline, API and React app | Author-reported initial build |
| Codex | FrameKind rename, interface redesign, security and export repairs, tests and deployment preparation | Repository changes and tests |
| Replit Agent | Inspected the imported project, checked runtime tools and Postgres, added the `postgresql-16` module and ran the build script | Actions observed in Replit; free quota stopped the task before full verification. See [Replit record](REPLIT_VERIFICATION.md). |
| Gemini on Google Cloud Vertex | Live transcription, sound detection and visual analysis | Complete local and hosted live reviews verified; see [readiness](SUBMISSION_READINESS.md). |

The instant sample uses authored fixtures. It is not a recording of a live model response. Do not describe this project as developed exclusively with Google tools. The organizer's restriction on Codex assistance means contest eligibility cannot be asserted from this repository.

## Replit setup

Core revision `5a5f9a0` from [GitHub](https://github.com/Abhinav0905/Google_All_Agentic_Cinema) was imported into the [Replit project](https://replit.com/@abhinav0905/GoogleAllAgenticCinema). The [public app](https://google-all-agentic-cinema--abhinav0905.replit.app) was published with the installer fix in `0edcde0`. A real hosted review completed all eight steps. Later testing found an idle Postgres connection failure; `c0fc1f3` adds connection checks before reuse. See [Replit verification](REPLIT_VERIFICATION.md) for the final deployed state and test evidence.

- Build command: `bash scripts/replit_build.sh`
- Run command: `bash scripts/replit_start.sh`
- Python 3.11 or 3.12, uv, Node 20+, FFmpeg/FFprobe. Replit uses Python 3.11.
- Build and startup share `.venv`; `uv sync --frozen --no-dev` installs the checked-in lockfile. Startup does not install packages.
- Use a single serving process and a single deployment instance. Jobs, progress events and the current request limiter are process-local. For Autoscale, set Publishing > Adjust settings > Machine configuration > Max machines to 1.
- Attach Replit Postgres for durable run history. Uploaded video, captions and AD files persist in the `qc_assets` table and restore after restart. Run history is in `qc_runs`; repairs and decisions have separate tables.

For the configured short-clip path, add `GOOGLE_SERVICE_ACCOUNT_JSON` and `GOOGLE_CLOUD_PROJECT` to Replit Secrets, with `GOOGLE_CLOUD_LOCATION=global`. Alternatively, add `VERTEX_API_KEY` where Google permits Vertex authorization keys. Credentials stay on the server. Inline video is capped at 14 MiB. Set the model IDs from `.env.example` and verify a real call before recording.

The optional GCS path requires ADC or `GOOGLE_SERVICE_ACCOUNT_JSON`, `GOOGLE_CLOUD_PROJECT`, `GCS_BUCKET` and suitable bucket permissions. Apply bucket CORS for the deployed app origin if using signed browser PUT uploads. Never paste credentials into Agent chat or commit them.

## Bounded Replit Agent task

This prompt was issued after import. The Agent performed part of the task before reaching its free quota. Subsequent manual checks and repairs are recorded separately; they are not completed Agent work.

> This is FrameKind, a FastAPI + React accessibility review app. Verify the imported repository builds and runs on Replit using scripts/replit_build.sh and scripts/replit_start.sh. Preserve the existing UI and Google-only runtime AI SDKs. Check Python, Node and FFmpeg availability, port binding and static asset serving. Attach Replit Postgres if available and verify that a sample run and its accepted repair survive a process restart for the same browser session. Fix any Replit-specific deployment issue you reproduce. Record the exact checks and files changed in docs/REPLIT_VERIFICATION.md. Do not expose secret values. Do not claim deployment success until the public URL works.

## Hosted acceptance checks

1. Open the public `.replit.app` URL in a new browser session.
2. Click **Step into a sample review** and inspect a missing-sound finding.
3. Accept one repair, export twice and compare downloads.
4. Start a real short-video run; confirm all three model steps succeed.
5. Reload history in the same session. Verify another browser session cannot open its run.
6. Keep the app available through the end of judging, October 8, 2026, and check the event schedule again before shutting it down.

Screenshots belong in `docs/screenshots/`; include only files that actually exist. Record no keys, personal account details or database passwords.
