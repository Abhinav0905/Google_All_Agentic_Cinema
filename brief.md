# CueCheck — Build Brief

You are building **CueCheck**, an accessibility QC agent for film and TV deliverables. It checks caption/SDH files and audio-description (AD) scripts against a chosen spec profile, explains every failure with a timestamp, fixes what can be fixed deterministically, and exports compliant files plus a report. It is our entry to the Agentic Cinema hackathon, **Replit track**, deadline **Wed Sep 9, 2:00 PM PDT**. Read this whole document before writing anything.

---

## 0. How we work together

1. Work **one phase at a time** (Section 15). At the end of each phase: run the tests, list the files you changed, list every assumption or unknown, then stop and wait for "go."
2. Business logic lives in plain Python modules with no framework imports. ADK, FastAPI and React are thin layers on top. Everything in `engine/` must be testable without network access.
3. **AI tooling allowlist, no exceptions**: `google-adk`, `google-genai`, `google-cloud-aiplatform`, `google-cloud-storage`, `google-cloud-speech`. Do not add LangChain, LlamaIndex, OpenAI, Anthropic, Hugging Face, or any other AI SDK, framework, or API. Ask before adding any dependency not listed in Section 14.
4. Thresholds and rules live in profile JSON files with a `source` note. Never hardcode a number in the engine.
5. Log every model call (model id, purpose, input size, duration) to the run log. Never log secrets or media.
6. No silent fallbacks. If a model call fails, the step is marked failed and the UI shows it. Mock or recorded outputs are for tests only.
7. Video bytes never pass through the app server. Browser → Cloud Storage via signed URL; Vertex AI reads the `gs://` URI.
8. Commit after each phase with a message that names the phase.

---

## 1. What this is and who it's for

Every title delivered to a streaming platform or broadcaster needs captions (usually SDH) and, increasingly, audio description. Regulators require them (FCC caption-quality rules and CVAA in the US, ADA/WCAG expectations, EU audiovisual and accessibility rules) and every platform publishes its own timed-text spec. QC today is a person scrubbing a timeline with a style guide open. Mechanical checkers exist; they do not tell you that a door slammed and nobody captioned it, that the speaker was off-screen and unnamed, or that the description talks over a line of dialogue.

**Users**: post-production and localization QC leads, indie distributors preparing deliverables, small streaming ops teams.

**Product promise**: upload a cut and its caption file, pick a profile, get a scored report in minutes, accept fixes, download compliant files.

**Judging criteria we are optimizing for** (equal weight): technological implementation, design (complete product, not a proof of concept), potential impact, quality of idea. Ties break on implementation first, so the rules engine and the multimodal steps must be solid before the UI gets pretty.

---

## 2. Hard constraints (hackathon compliance)

- Runtime AI: **Gemini on Vertex AI only**, called through `google-genai` (Vertex backend) and orchestrated with `google-adk`. Optional: Cloud Speech-to-Text v2 for word timing.
- Hosting: the finished app runs on **Replit** (`*.replit.app`). Google Cloud is used *from* the app: Vertex AI, Cloud Storage, optionally Speech-to-Text.
- Repo: public GitHub, **Apache-2.0** `LICENSE` at root so GitHub shows it in the About box.
- Demo materials (video, screenshots): no third-party footage, logos, trademarks, or platform names. Profile names are generic ("Adult broadcast," "Children's"). The sample clip is our own footage.
- New code only; nothing copied from prior projects.

---

## 3. Architecture and repo layout

```
cuecheck/
  engine/            pure Python: parsing, profiles, rules, alignment, fixer, scoring, export
  agents/            google-adk agents wrapping engine steps + Gemini calls; SequentialAgent pipeline
  api/               FastAPI app: runs, SSE trace, decisions, export; serves web/dist
  web/               React + Vite + Tailwind SPA
  profiles/          adult.json, kids.json
  samples/           clip.mp4 (placeholder until real footage), captions_bad.srt, ad_script.srt, expected_findings.json
  tests/             pytest; fixtures/ holds recorded Gemini outputs for offline tests
  docs/              ARCHITECTURE.md (Mermaid diagram), TOOLING.md, DEMO_SCRIPT.md
  scripts/           smoke_gcp (one Gemini call + one GCS round-trip), run_sample (CLI end-to-end)
  LICENSE  README.md  pyproject.toml  .env.example  .replit  replit.nix (Replit phase)
```

Flow: browser uploads to GCS with signed URLs → `POST /runs/{id}/start` → FastAPI background task runs the ADK pipeline → steps publish trace events over SSE → findings, fixes, scorecard stored on the run → user accepts/rejects fixes → export regenerates files from accepted fixes.

---

## 4. Data model (Pydantic, in `engine/models`)

| Object | Fields |
|---|---|
| **Cue** | index, start_ms, end_ms, lines (list of str), raw_text, kind (`caption`, `ad`) |
| **Segment** (transcript) | start_ms, end_ms, text, speaker_label (optional), speaker_on_screen (bool, from visual pass), confidence |
| **AudioEvent** | t_ms, label, salience (`plot`, `ambient`), source |
| **VisualEvent** | t_ms, label, essential (bool), kind (`action`, `scene_change`, `onscreen_text`, `expression`) |
| **Finding** | id, code, severity (`error`, `warning`, `info`), cue_index (optional), start_ms, end_ms, message, evidence (str), spec_ref (str), fix_id (optional) |
| **Fix** | id, finding_ids, type, before (Cue or null), after (Cue or null), auto (bool), status (`proposed`, `accepted`, `rejected`) |
| **Scorecard** | per-dimension: score (0–1), threshold, status (`pass`, `warn`, `fail`), counts |
| **Run** | id, created_at, profile_id, sdh_mode, has_ad, media_uri, caption_uri, ad_uri, status, steps (trace), findings, fixes, scorecard, exports |

---

## 5. Spec profiles (`profiles/*.json`)

Defaults are modeled on widely used streaming timed-text style guides. Each value carries a `source` string. All editable.

| Rule | Adult | Kids | Notes |
|---|---|---|---|
| max_cps (chars/sec, spaces counted, tags excluded) | 20 | 17 | reading speed |
| max_chars_per_line | 42 | 42 | |
| max_lines | 2 | 2 | |
| min_duration_ms | 833 | 833 | 5/6 s |
| max_duration_ms | 7000 | 7000 | |
| min_gap_ms | 83 | 83 | ~2 frames at 24 fps |
| sync_tolerance_ms | 500 | 500 | cue start vs matched speech start |
| ad_overlap_tolerance_ms | 250 | 250 | AD over dialogue |
| ad_max_wpm | 180 | 160 | warning only |
| pass thresholds | accuracy ≥ 0.98, sync ≥ 0.95, completeness ≥ 0.98, readability ≥ 0.95, sdh ≥ 0.90, ad ≥ 0.90 | same | warn band = pass − 0.05 |

---

## 6. Findings catalogue

Deterministic checks run in `engine/rules` with no model. Semantic checks use Gemini outputs produced in the ground-truth step and are then judged deterministically against those outputs.

| Code | Check | Truth source | Severity | Auto-fix |
|---|---|---|---|---|
| DUR_MIN | cue shorter than min_duration | captions | error | extend into gap |
| DUR_MAX | cue longer than max_duration | captions | warning | split |
| CPS | chars/sec over max_cps | captions | error | extend, else split, else manual |
| CPL | line over max_chars_per_line | captions | error | re-wrap |
| LINES | more lines than max_lines | captions | error | re-wrap/split |
| GAP_MIN | gap to next cue under min_gap | captions | warning | trim end |
| OVERLAP | cue overlaps next cue | captions | error | trim end |
| ORDER | non-monotonic timing | captions | error | manual |
| EMPTY | blank cue | captions | warning | delete |
| TAG_FORMAT | sound tag not bracketed / music not marked | captions | info | normalize |
| SYNC_OFFSET | cue start vs matched segment start beyond tolerance | transcript | error | global shift if consistent |
| MISSING_DIALOGUE | speech segment with no matching cue | transcript | error | insert cue from transcript (propose) |
| EXTRA_CAPTION | cue with no matching speech and no tag | transcript | info | none |
| ACCURACY_LOW | word error rate of cue vs matched segment above 0.15 | transcript | warning | propose transcript text |
| SDH_MISSING_SFX | salient audio event with no tagged cue in [t−1 s, t+2 s] | audio events | error if `plot`, warning if `ambient` | insert tag cue (propose) |
| SDH_MISSING_SPEAKER_ID | off-screen speech with no speaker label on the cue | segments + visual pass | error | prepend label (propose) |
| AD_OVERLAPS_DIALOGUE | AD cue overlaps speech beyond tolerance | AD + transcript | error | retime AD cue into nearest silence (propose) |
| AD_GAP | essential visual event with no AD cue in [t−1 s, t+4 s] | visual events | error | none (report) |
| AD_ONSCREEN_TEXT | on-screen text not read by AD or captions | visual events | warning | none (report) |
| AD_READING_RATE | AD cue words/min over ad_max_wpm | AD | warning | none |

SDH_* codes run only when `sdh_mode` is on. AD_* codes run only when an AD script is provided.

---

## 7. Pipeline (ADK `SequentialAgent`, `agents/pipeline`)

Each step is an ADK agent that reads and writes run state under named keys and emits one trace event on start and one on finish (status, duration, short summary). Model-backed steps request **structured JSON output with a schema**.

1. **Ingest** (deterministic): fetch caption and AD files from GCS, parse SRT/WebVTT into Cues, validate media URI and duration (reject clips over 5 minutes for now), load profile.
2. **Transcribe** (Gemini Flash, video from `gs://`): segments with start/end ms, text, and a coarse speaker label (Speaker 1, 2…). If `ENABLE_STT` is true, use Speech-to-Text v2 for word timing and Gemini only for text cleanup.
3. **Listen** (Gemini Flash, same media): non-speech audio events with timestamp, label, salience. Ask it to include music start/stop.
4. **Look** (Gemini Pro if latency allows, else Flash): for each speech segment, is the speaker visible and speaking on screen; plus visual events (scene changes, essential actions, on-screen text, expressions that carry plot).
5. **Rules** (deterministic): all caption-only checks from Section 6.
6. **Align** (deterministic): match cues to segments by normalized token similarity within ±5 s; compute per-cue offset; SYNC_OFFSET, MISSING_DIALOGUE, EXTRA_CAPTION, ACCURACY_LOW; median offset for a possible global shift.
7. **Semantic checks** (deterministic over model outputs): SDH_* and AD_* codes.
8. **Score and plan fixes** (deterministic): scorecard per Section 9, fix proposals per Section 8, persist everything, emit `run.complete`.

Prompts for steps 2–4 live in `agents/prompts/` as plain text files with the output schema next to them. Keep them short, ask for timestamps in milliseconds, and ask for `null` rather than a guess when the model is unsure.

Model ids come from config (`GEMINI_FLASH_MODEL`, `GEMINI_PRO_MODEL`). Verify both with the smoke script before Phase 2; do not assume a version.

---

## 8. Fixer (`engine/fixer`)

- **Extend**: push end_ms later up to `next.start_ms − min_gap_ms` to satisfy DUR_MIN or reduce CPS.
- **Re-wrap**: break text at clause boundaries (punctuation, then conjunctions, then the last space before the limit) into ≤ max_lines lines of ≤ max_chars_per_line.
- **Split**: divide a cue into two at a clause boundary, time proportional to character count, both halves ≥ min_duration; if impossible, mark manual.
- **Trim**: pull end_ms back to fix GAP_MIN/OVERLAP.
- **Global shift**: if `|median offset| > sync_tolerance` and at least 80% of matched cues sit within 300 ms of the median, propose one shift for all cues from the first affected cue onward.
- **Insert tag cue**: from SDH_MISSING_SFX, create a bracketed cue at the event time (or prepend the tag to an overlapping cue).
- **Prepend speaker label**: from SDH_MISSING_SPEAKER_ID, using the label from the visual pass.
- **Retime AD**: move the AD cue into the nearest silence that fits its duration; if none, mark manual.

Every fix stores `before` and `after`. Nothing applies until accepted. Export regenerates from the accepted set and re-runs the deterministic rules on the result so the report shows before/after scores.

---

## 9. Scorecard (`engine/scoring`)

| Dimension | Formula |
|---|---|
| Accuracy | 1 − mean word error rate over matched cues |
| Synchronicity | matched cues within tolerance ÷ matched cues |
| Completeness | speech segments with a match ÷ speech segments |
| Readability | 1 − cues with any DUR/CPS/CPL/LINES/GAP violation ÷ cues |
| SDH coverage | tagged salient events ÷ salient events (weighted 0.5) + labeled off-screen segments ÷ off-screen segments (0.5) |
| AD coverage | described essential events ÷ essential events; overlap violations listed separately |

The first four map to the FCC's caption-quality dimensions; name them that way in the UI copy.

---

## 10. API (`api/`)

| Method + path | Purpose |
|---|---|
| POST `/api/runs` | create run; returns run_id and signed PUT URLs for video, captions, AD |
| POST `/api/runs/{id}/start` | body: profile_id, sdh_mode, has_ad; starts pipeline in background |
| GET `/api/runs/{id}/events` | SSE stream of trace events until `run.complete` or `run.failed` |
| GET `/api/runs/{id}` | status, scorecard, findings, fixes, export links |
| POST `/api/runs/{id}/fixes/{fix_id}` | body: decision `accept` or `reject` |
| GET `/api/runs/{id}/export?format=vtt\|srt\|json\|report` | files regenerated from accepted fixes; `report` is HTML (PDF is stretch) |
| POST `/api/runs/sample` | create and start a run from `samples/` |
| GET `/api/runs` | history |
| GET `/api/health` | which GCP services are configured (booleans only) |

Signed URL TTL 15 minutes. Video uploads capped at 500 MB, captions at 2 MB.

---

## 11. UI (`web/`)

Screens:

1. **New QC**: drop zones for video, captions, optional AD script; profile selector (Adult broadcast / Children's); SDH toggle; "Run QC" and a "Load sample" button that works with zero uploads.
2. **Run**: left column shows the pipeline trace (8 steps, live status, duration, one-line summary). When complete, the main area shows the **scorecard** (six cards, pass/warn/fail), then the **video with a marker strip** underneath (one marker per finding, colored by severity), then the **findings table** (filter by code and severity, sort by time).
3. **Finding drawer**: clicking a row seeks the video to `start_ms − 1 s`, shows cue text, the evidence, the spec reference, and the proposed fix as a before/after diff with Accept / Reject.
4. **Export**: after decisions, "Apply and export" produces VTT, SRT, JSON, and the HTML report with before/after scores.
5. **History**: past runs (Replit Postgres in Phase 6; in-memory before that).

Visual direction: dark, editorial, timecode-first. Feels like a QC bay, not a SaaS dashboard. Sans-serif for text, monospace for timecodes. Severity colors: error red, warning amber, info slate, pass green. Every timestamp in the UI is clickable and seeks the video. Empty states, loading states, and error states all designed, not defaulted. No logos of any third party anywhere.

---

## 12. Sample data and demo mode

`samples/clip.mp4` is a 60–90 second original clip (a placeholder until the real footage lands; the pipeline must not depend on its content). `samples/captions_bad.srt` seeds these defects so the demo has something to find:

1. three cues over 20 cps
2. one cue with three lines
3. every cue from 0:30 onward shifted +1.2 s
4. one line of dialogue missing entirely
5. no sound tags, while the clip has two obvious sound events
6. one off-screen line with no speaker label

`samples/ad_script.srt` has one AD cue that overlaps dialogue and leaves one essential visual event undescribed. `samples/expected_findings.json` is the golden file for the deterministic codes.

---

## 13. Testing

- Unit tests for every code in Section 6 using tiny synthetic SRTs (one file per code).
- Golden test: deterministic findings on `captions_bad.srt` equal `expected_findings.json`.
- Alignment tests with synthetic transcripts: consistent shift, partial shift, missing line, paraphrased line.
- Fixer tests: each fix type, plus "fix never violates another rule" (extend respects gap, split respects min duration).
- Model steps: tests run against recorded JSON fixtures in `tests/fixtures/`; a marked `live` test suite hits Vertex when `RUN_LIVE=1`.
- `ruff` clean. `pytest` green at every phase gate.

---

## 14. Configuration and dependencies

Env vars (`.env.example` documents all of them): `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION`, `GOOGLE_GENAI_USE_VERTEXAI=true`, `GCS_BUCKET`, `GEMINI_FLASH_MODEL`, `GEMINI_PRO_MODEL`, `ENABLE_STT` (default false), `GOOGLE_SERVICE_ACCOUNT_JSON` (Replit secret; on startup write it to a temp file and point `GOOGLE_APPLICATION_CREDENTIALS` at it), `DATABASE_URL` (Replit Postgres, Phase 6), `APP_BASE_URL`, `SIGNED_URL_TTL_SECONDS`.

Dependency allowlist: `google-adk`, `google-genai`, `google-cloud-storage`, `google-cloud-speech` (optional), `fastapi`, `uvicorn`, `pydantic`, `python-multipart`, `sse-starlette`, `srt`, `webvtt-py`, `jinja2`, `sqlalchemy` + `psycopg` (Phase 6), `pytest`, `ruff`. Frontend: `react`, `vite`, `tailwindcss`, `lucide-react`. Ask before adding anything else.

---

## 15. Phases and definition of done

| Phase | Time box | Build | Done when |
|---|---|---|---|
| **0 Scaffold** | 45 min | repo layout, LICENSE, pyproject, ruff, pytest, `.env.example`, `scripts/smoke_gcp` | smoke script makes one Gemini call on Vertex and one GCS round-trip; `pytest` runs (even if empty) |
| **1 Caption engine** | 3 h | parsers, models, profiles, all caption-only rules, VTT/SRT export | every caption-only code has a passing test; golden test passes; export→parse round-trip is lossless |
| **2 Ground truth + semantics** | 3 h | GCS upload helpers, Transcribe/Listen/Look prompts + schemas, Align, SDH and AD checks, recorded fixtures | `scripts/run_sample` runs end to end from the CLI against Vertex and prints findings; fixtures saved; offline tests pass |
| **3 Orchestration + fixes + score** | 2 h | ADK SequentialAgent, trace events, scorecard, fixer, HTML report | `adk web` shows the pipeline running; CLI produces report with before/after scores |
| **4 API + UI** | 4 h | FastAPI endpoints, SSE, React screens 1–4 | full flow in the browser locally; "Load sample" works; clicking a finding seeks the video; accept/reject changes the export |
| **5 Polish + docs** | 1.5 h | empty/loading/error states, timecode formatting, `docs/ARCHITECTURE.md` with Mermaid diagram | a stranger can run the sample without instructions |
| **6 Replit** | 2–3 h | see Section 16 | public `replit.app` URL runs the sample end to end |
| **7 Submission** | 2 h | README, `docs/TOOLING.md`, `docs/DEMO_SCRIPT.md`, video, Devpost form | checklist in Section 17 fully ticked |

Stretch, only after Phase 7 is safe: Speech-to-Text v2 word timing; deploy the pipeline agent to Vertex AI Agent Engine and call it from the app; PDF report.

If Phase 4 runs long, cut in this order: History screen → AD checks in the UI (keep them in the report) → marker strip (keep the table).

---

## 16. Replit handoff (Phase 6)

Push to GitHub, import the repo into Replit, then give **Replit Agent** these tasks, in order, and keep screenshots of each session for `docs/TOOLING.md`:

1. Configure the workspace: Python 3.11 + Node; build command builds `web/` into `web/dist`; run command starts uvicorn on the Replit port.
2. Add the secrets from `.env.example`.
3. Provision Replit Postgres and persist runs, findings, fixes and decisions (replace the in-memory store; SQLAlchemy models already exist or Replit Agent writes them).
4. Build the History screen against Postgres, so Replit Agent's contribution is visible in the product.
5. Deploy (Reserved VM or Autoscale, whichever keeps SSE stable) and confirm the public URL runs "Load sample" end to end.
6. Keep the deployment live through **Oct 7** (judging window).

---

## 17. Submission checklist (Phase 7)

- [ ] Devpost track: **Replit**. Partner integration field: "Replit Agent (development) + Replit Deployments (hosting)" with the live URL.
- [ ] Hosted URL is the `replit.app` deployment and "Load sample" works from a fresh browser.
- [ ] Repo public; Apache-2.0 shows in the GitHub About box; README states which Google Cloud services are called and in which files (`agents/`, `engine/gcs`), and what Replit Agent built.
- [ ] `docs/TOOLING.md`: Antigravity (Gemini) for engine/api/web, Replit Agent for Phase 6, Gemini CLI if used. Screenshots included.
- [ ] Demo video ≤ 3 minutes, English, public on YouTube or Vimeo, shows the product functioning as built, our own footage only, no third-party names or logos. Shot list in `docs/DEMO_SCRIPT.md`: 0:00 problem (25 s) → 0:25 upload and run with live trace → 1:10 scorecard and findings, click to seek → 1:50 accept fixes, before/after diff → 2:20 export and report → 2:45 architecture card.
- [ ] Devpost text covers: features, technologies, data sources (our sample clip; profiles modeled on public style guides), findings and learnings.
- [ ] Deployment stays up through Oct 7.

---

Start with Phase 0. Report back before Phase 1.