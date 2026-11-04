# Tooling

CueCheck was built in two environments. The engine, agents, API, and QC bay were written in **Antigravity** (Gemini). Phase 6 — workspace, secrets, Postgres, History, and the public deployment — is the **Replit Agent** handoff.

This file is the paste-ready brief for that handoff. After each Replit Agent session, drop a screenshot into `docs/screenshots/` and link it in the table at the bottom.

## What each tool owns

| Tool | What it built | Where to look |
|---|---|---|
| Antigravity (Gemini) | Caption/SDH/AD engine, ADK pipeline, FastAPI, React QC bay, offline sample | `engine/`, `agents/`, `api/` (except persistence), `web/`, `profiles/`, `samples/` |
| Replit Agent | Workspace, secrets, Postgres persistence, History against the database, `replit.app` deploy | `.replit`, `replit.nix`, `scripts/replit_*.sh`, `api/db.py`, History screen |
| Gemini CLI | Not used | — |

Google Cloud services called at runtime:

- Vertex AI Gemini — `agents/multimodal.py`, `scripts/smoke_gcp.py`
- Cloud Storage signed URLs — `engine/gcs.py`, `api/main.py`
- Speech-to-Text v2 — optional, `ENABLE_STT=false` by default

## Replit Agent tasks (run in this order)

Give Replit Agent one task at a time. Keep a screenshot of each session.

### 1. Configure the workspace

```
This repo is CueCheck. Configure the Replit workspace for Python 3.11 and Node 20.

Use the files already in the repo:
- .replit
- replit.nix
- scripts/replit_build.sh  (pip install -e . and npm run build in web/)
- scripts/replit_start.sh  (serves FastAPI + web/dist on $PORT)

Build command must produce web/dist. Run command must start:
  python -m uvicorn api.main:app --host 0.0.0.0 --port $PORT

Do not change the Python package layout. Do not add AI SDKs other than google-adk and google-genai.
```

### 2. Add secrets

```
Copy every variable from .env.example into Replit Secrets.

Required for live Vertex / GCS:
GOOGLE_CLOUD_PROJECT
GOOGLE_CLOUD_LOCATION=us-central1
GOOGLE_GENAI_USE_VERTEXAI=true
GCS_BUCKET
GEMINI_FLASH_MODEL=gemini-2.5-flash
GEMINI_PRO_MODEL=gemini-2.5-pro
GOOGLE_SERVICE_ACCOUNT_JSON   (full service-account JSON; the app writes it to a temp file on boot)

Optional:
ENABLE_STT=false
SIGNED_URL_TTL_SECONDS=900
APP_BASE_URL=https://<this-repl>.replit.app

DATABASE_URL is set automatically when you attach Replit Postgres. Do not invent one.
```

### 3. Provision Postgres and persist QC objects

```
Attach Replit Postgres to this Repl. DATABASE_URL will be injected.

SQLAlchemy models already exist in api/db.py:
- qc_runs
- qc_findings
- qc_fixes
- qc_decisions

api/store.py already writes those tables. Confirm:
- Load sample creates rows in qc_runs, qc_findings, qc_fixes
- Accept / Reject a fix writes qc_decisions
- Restarting the Repl still lists the run on History

If the driver URL is postgres://, api/db.py rewrites it to postgresql+psycopg://.
Do not replace the store with a new ORM. Do not add Redis.
```

### 4. History screen against Postgres

```
The History screen (web/src/App.jsx) already reads GET /api/runs.
That list is backed by the database, not process memory.

Confirm after a Repl restart:
1. History still shows earlier runs
2. Clicking a row opens the completed scorecard and findings
3. The health line shows DATABASE POSTGRES

If History is empty after restart, the store is not loading from qc_runs. Fix api/store.py get/list, not the React table.
```

### 5. Deploy

```
Deploy on Autoscale (or Reserved VM if SSE drops on Autoscale).

Public URL must be https://*.replit.app.
From a fresh browser, with no local files:
1. Open the URL
2. Click Load sample
3. Wait for the eight-step trace to reach run.complete
4. Open a finding, accept one fix, export SRT

Keep this deployment live through 7 October.
```

## Local database (no Replit)

If `DATABASE_URL` is unset, the API uses SQLite at `.data/cuecheck.sqlite`. History still survives a local uvicorn restart. Tests force an in-memory SQLite engine.

## Screenshots

| Session | File | Notes |
|---|---|---|
| 1 Workspace (Python 3.11 + Node, build/run) | `docs/screenshots/01-workspace.png` | Add after the Replit session |
| 2 Secrets from `.env.example` | `docs/screenshots/02-secrets.png` | Redact key material |
| 3 Postgres + persisted runs | `docs/screenshots/03-postgres.png` | Tables visible |
| 4 History after restart | `docs/screenshots/04-history.png` | Same run id as session 3 |
| 5 Public Load sample | `docs/screenshots/05-deploy.png` | `*.replit.app` in the address bar |
