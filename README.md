# CueCheck

> Accessibility QC agent for film and TV deliverables.

CueCheck checks caption/SDH files and audio-description (AD) scripts against spec profiles (FCC standards, streaming timed-text style guides), explains every defect with a millisecond timestamp, fixes deterministic issues, and exports compliant files and audit reports.

Built for the **Agentic Cinema Hackathon** (Replit Track).

---

## Architecture & Layout

```
cuecheck/
  engine/            Pure Python: parsing, profiles, rules, alignment, fixer, scoring, export
  agents/            google-adk agents wrapping engine steps + Gemini calls; SequentialAgent pipeline
  api/               FastAPI app: runs, SSE trace, decisions, export; serves web/dist
  web/               React + Vite + Tailwind SPA
  profiles/          adult.json, kids.json
  samples/           clip.mp4, captions_bad.srt, ad_script.srt, expected_findings.json
  tests/             pytest suite; fixtures/ holds recorded Gemini outputs for offline tests
  docs/              ARCHITECTURE.md, TOOLING.md, DEMO_SCRIPT.md
  scripts/           smoke_gcp.py, run_sample.py
  LICENSE            Apache-2.0
```

---

## Google Cloud Services Used

- **Vertex AI (Gemini 2.5 Flash / Pro)**: Multimodal video transcription, audio event listening, and visual pass (speaker visibility and onscreen text detection). Used in `agents/` and `scripts/smoke_gcp.py`.
- **Cloud Storage (GCS)**: Secure video and asset storage via signed URLs. Used in `api/` and `scripts/smoke_gcp.py`.
- **Cloud Speech-to-Text v2** *(optional)*: Precise word timing when enabled.

---

## Getting Started

### 1. Setup Virtual Environment
```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 2. Configure Environment
Copy `.env.example` to `.env` and fill in your GCP project and bucket details:
```bash
cp .env.example .env
```

### 3. Verify GCP Connectivity
Run the smoke test script:
```bash
python scripts/smoke_gcp.py
```

### 4. Run Tests
```bash
pytest
ruff check .
```

---

## License

Licensed under the [Apache-2.0 License](LICENSE).
