# CueCheck

Accessibility QC for captions, SDH, and audio description. Upload a cut, pick a spec profile, get a scored report with timestamps, accept fixes, export compliant files.

## Run the sample

Python 3.11+, Node 18+. No cloud account required.

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cd web && npm install && npm run build && cd ..
uvicorn api.main:app --port 8000
```

Open http://localhost:8000 and click **Load sample**.

That run uses `samples/captions_bad.srt` and recorded Gemini fixtures. Click a timecode to seek. Accept or reject a fix. Export SRT, VTT, JSON, or the HTML report.

CLI equivalent:

```bash
python scripts/run_sample.py
```

`adk web .` loads `agents/agent.py` (`root_agent`). Send any message to run the same sample pipeline.

## Optional: Vertex and Cloud Storage

Copy `.env.example` to `.env` only if you want live Gemini or signed video uploads.

```bash
cp .env.example .env
python scripts/smoke_gcp.py
```

Video never passes through the app server. The browser PUTs the picture to GCS. Vertex reads the `gs://` URI.

## Tests

```bash
pytest
ruff check .
```

## What lives where

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the mermaid diagrams.

| Path | Role |
|---|---|
| `engine/` | Pure Python: parse, rules, align, fix, score, export |
| `agents/` | ADK SequentialAgent + Gemini (Vertex) |
| `api/` | FastAPI, SSE, signed URLs |
| `web/` | React QC bay |
| `profiles/` | Adult broadcast / Children's thresholds |
| `samples/` | Seeded defective captions + AD script |

Google Cloud used at runtime: Vertex AI Gemini (`agents/multimodal.py`, `scripts/smoke_gcp.py`), Cloud Storage signed URLs (`engine/gcs.py`, `api/main.py`). Speech-to-Text v2 is optional and off by default.

History is stored in SQLite locally (`.data/cuecheck.sqlite`) or Replit Postgres when `DATABASE_URL` is set. See [docs/TOOLING.md](docs/TOOLING.md) for the Replit Agent handoff.

## Replit

Import this repo into Replit. The workspace uses Python 3.11 + Node. `scripts/replit_build.sh` builds `web/dist`. `scripts/replit_start.sh` serves FastAPI on `$PORT`. Attach Replit Postgres so History survives a restart. Paste-ready Agent tasks are in [docs/TOOLING.md](docs/TOOLING.md).

## License

Apache-2.0. See [LICENSE](LICENSE).
