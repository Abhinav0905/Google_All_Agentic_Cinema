# FrameKind judge evidence map

Verified locally on September 8, 2026. FrameKind is a caption and audio-description review workspace for film editors. It proposes repairs, lets an editor approve or keep the original, and exports the resulting captions and review report.

This map records implementation and test evidence. It does not establish contest eligibility. The development history includes Google Antigravity and Codex; see [tooling disclosure](TOOLING.md). The organizer's [AI-tool clarification](https://agentic-cinema.devpost.com/forum_topics/44644-question-about-the-ai-usage-limitation-grafana-track) covers development assistance as well as runtime AI. A Google-only runtime does not resolve that conflict.

## Implementation and evidence

| Capability | Where to inspect | Verified evidence and limits |
|---|---|---|
| Google Cloud Gemini at runtime | [Vertex client and media inputs](../agents/multimodal.py#L65), [live input selection](../api/main.py#L537) | Two local uploaded-video reviews completed all eight steps with real Vertex calls. The runtime used Gemini 2.5 Flash and Pro through ADC. This verifies the local integration, not a hosted deployment. |
| Ordered agent workflow | [ADK pipeline](../agents/pipeline.py#L511), [pipeline tests](../tests/test_pipeline.py) | ADK `SequentialAgent` registers ingest, transcribe, listen, look, caption rules, alignment, semantic checks and scoring/repair planning. This is an application running ADK; no managed Agent Engine deployment is claimed. |
| Honest analysis modes | [pipeline execution](../agents/pipeline.py#L531), [scorecard](../engine/scoring.py#L35), [mode regression](../tests/test_pipeline.py#L90) | `live` analyzes uploaded media. `sample` uses authored reference annotations. `caption_only` checks timed text and leaves media-dependent dimensions unassessed. Custom uploads cannot silently receive sample findings. |
| Picture, evidence and repair in one view | [review workspace](../web/src/components/RunView.jsx) | Browser review completed with 29 findings. The editor opened the phone finding, approved its repair and downloaded SRT. Findings can seek the player to a timecode. Model event labels varied between runs, so the editor must check each proposal. |
| Reversible decisions and real exports | [fix decisions](../api/main.py#L668), [exports](../api/main.py#L699), [repair regressions](../tests/test_fixer.py#L323) | The independent live API check approved a repair and obtained identical repeated SRT exports. Original captions stay unchanged. Conflicting accepted repairs are rejected. Scores after approved changes are recalculated. |
| Saved reviews and uploaded media | [database models](../api/db.py#L76), [persistence](../api/db.py#L179), [database tests](../tests/test_db.py#L118) | SQLite persistence was exercised locally. Tests cover cache reload, ownership, recorded decisions and media restoration after database reopen. Replit Postgres is supported but hosted persistence still needs verification. |
| Private anonymous sessions | [session and origin checks](../api/security.py#L65), [route isolation test](../tests/test_api.py#L113) | The live API check confirmed another browser session receives 404 for the run. Ownership also protects events, exports and media. There is no mandatory signup. Clearing the session cookie loses access to that browser's review history. |
| Bounded uploads and working playback | [body limit](../api/security.py#L24), [media endpoint](../api/main.py#L725), [upload tests](../tests/test_api.py#L245) | Inline MP4 uploads are capped at 14 MiB. The live check received HTTP 206 for a byte-range media request. Optional GCS playback uses a signed redirect; that branch has mocked tests, not a deployed cloud-storage demonstration. |
| Reliable terminal state | [API pipeline owner](../api/main.py#L313), [failure tests](../tests/test_api.py#L385), [duplicate observation test](../tests/test_db.py#L168) | A live run exposed duplicate finding IDs. Canonical event IDs and database projection keys were repaired; both subsequent live runs completed. Completion is published after persistence. Failure events still reach the browser if saving the failure state fails. |
| Sample asset provenance | [scene notes](../samples/README.md), [provenance JSON](../samples/clip.provenance.json), [renderer](../scripts/create_demo_media.py) | Original 60-second illustrated scene, synthesized phone/door effects and 13 Google Cloud Text-to-Speech tracks. Sample fixtures are authored examples, not an accuracy benchmark. |
| Public source and license | [GitHub repository](https://github.com/Abhinav0905/Google_All_Agentic_Cinema), [Apache-2.0 license](../LICENSE), [setup](../README.md) | FrameKind core revision `5a5f9a0` was pushed and the remote revision verified. These final evidence documents need a follow-up push. The existing license is Apache-2.0. |
| Replit development and hosting | [.replit](../.replit), [build](../scripts/replit_build.sh), [start](../scripts/replit_start.sh), [verification task](TOOLING.md) | Repository import is complete and the automatic Agent setup task has started. No completed Agent verification record or public app URL is verified yet. The [Replit track requirements](https://agentic-cinema.devpost.com/details/replit-resources) require both Agent use and Replit hosting. |

## Verification record

- Full local suite: **108 passed**, with 16 dependency deprecation warnings.
- Ruff checks passed for `engine`, `agents`, `api` and `tests`; `git diff --check` passed.
- Browser live review: all eight steps completed, 29 findings, phone-caption repair approved and SRT downloaded.
- Independent live API review: all eight steps completed in 51.16 seconds, 24 findings and 11 repair proposals. Repeated SRT exports matched, cross-session access was denied, and range playback worked.
- The different finding counts are model variation, not a fixed expected score. These runs establish operation; they do not measure precision or recall.

The local verification workspace retains the live run and check summary. Do not publish session cookies, credentials or account screenshots as evidence. The remaining public proof is tracked in [submission readiness](SUBMISSION_READINESS.md).

## Submission assets

The [cover](screenshots/framekind-cover.png), [recording script](DEMO_SCRIPT.md), sample media and setup instructions exist. The Devpost draft has the FrameKind title, story, repository link and cover saved. Additional-information answers, the public app URL and the public demo video still need completion. The entry has not been formally submitted.

The [official rules](https://agentic-cinema.devpost.com/rules) require public source, a working project demonstration and a publicly visible YouTube or Vimeo video. Keep the video within three minutes and provide English narration or subtitles. The published deadline is September 9, 2026 at 2:00 p.m. PDT. Recheck the live form before the final submission.
