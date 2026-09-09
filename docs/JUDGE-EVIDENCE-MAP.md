# FrameKind judge evidence map

Evidence updated September 9, 2026. FrameKind is a caption and audio-description review workspace for film editors. It proposes repairs, lets an editor approve or keep the original, and exports the resulting captions and review report.

**[Public FrameKind app](https://google-all-agentic-cinema--abhinav0905.replit.app)**: runtime revision `c0fc1f3`. Earlier hosted live analysis, repair export, session isolation and range playback passed on `0edcde0`. The browser sample's findings, approved decision and identical export survived republishing to the new revision.

An idle-time `POST /api/runs` failure was traced to a terminated Postgres connection. The `pool_pre_ping` fix is deployed in `c0fc1f3`, with a closed-connection regression in the 109-test local suite. A fresh browser live review completed all eight steps on this revision. Review creation returned HTTP 201 before and after 180.6 seconds of client idle time.

This map records implementation and test evidence. It does not establish contest eligibility. The development history includes Google Antigravity and Codex; see [tooling disclosure](TOOLING.md). The organizer's [AI-tool clarification](https://agentic-cinema.devpost.com/forum_topics/44644-question-about-the-ai-usage-limitation-grafana-track) covers development assistance as well as runtime AI. A Google-only runtime does not resolve that conflict.

## Implementation and evidence

| Capability | Where to inspect | Verified evidence and limits |
|---|---|---|
| Google Cloud Gemini at runtime | [Vertex client and media inputs](../agents/multimodal.py#L65), [live input selection](../api/main.py#L537) | Two local reviews and one hosted uploaded-video review completed all eight steps with real Vertex calls. The hosted run used Gemini 2.5 Flash and Pro through ADC and finished in 48.16 seconds. |
| Ordered agent workflow | [ADK pipeline](../agents/pipeline.py#L511), [pipeline tests](../tests/test_pipeline.py) | ADK `SequentialAgent` registers ingest, transcribe, listen, look, caption rules, alignment, semantic checks and scoring/repair planning. This is an application running ADK; no managed Agent Engine deployment is claimed. |
| Honest analysis modes | [pipeline execution](../agents/pipeline.py#L531), [scorecard](../engine/scoring.py#L35), [mode regression](../tests/test_pipeline.py#L90) | `live` analyzes uploaded media. `sample` uses authored reference annotations. `caption_only` checks timed text and leaves media-dependent dimensions unassessed. Custom uploads cannot silently receive sample findings. |
| Picture, evidence and repair in one view | [review workspace](../web/src/components/RunView.jsx) | Browser review completed with 29 findings. The editor opened the phone finding, approved its repair and downloaded SRT. Findings can seek the player to a timecode. Model event labels varied between runs, so the editor must check each proposal. |
| Reversible decisions and real exports | [fix decisions](../api/main.py#L668), [exports](../api/main.py#L699), [repair regressions](../tests/test_fixer.py#L323) | Local and hosted live API checks approved a repair and obtained identical repeated SRT exports. The public browser sample also exported its approved phone caption. Original captions stay unchanged. Conflicting accepted repairs are rejected; scores are recalculated after approved changes. |
| Saved reviews and uploaded media | [database models](../api/db.py#L76), [persistence](../api/db.py#L179), [database tests](../tests/test_db.py#L118) | Local tests cover database reopen and media restoration. In production, sample `595edd8f` retained 19 findings and its approved edit after republishing. Its player loaded 01:00 metadata and the new SRT matched the pre-republish file byte for byte. |
| Private anonymous sessions | [session and origin checks](../api/security.py#L65), [route isolation test](../tests/test_api.py#L113) | Local and hosted live checks confirmed another browser session receives 404 for the run. Ownership also protects events, exports and media. There is no mandatory signup. Clearing the session cookie loses access to that browser's review history. |
| Bounded uploads and working playback | [body limit](../api/security.py#L24), [media endpoint](../api/main.py#L725), [upload tests](../tests/test_api.py#L245) | Inline MP4 uploads are capped at 14 MiB. Local and hosted checks received HTTP 206 for byte-range media requests. Optional GCS playback uses a signed redirect; that branch has mocked tests, not a deployed cloud-storage demonstration. |
| Reliable terminal state | [API pipeline owner](../api/main.py#L313), [failure tests](../tests/test_api.py#L385), [duplicate observation test](../tests/test_db.py#L168) | A live run exposed duplicate finding IDs. Canonical event IDs and database projection keys were repaired; both subsequent live runs completed. Completion is published after persistence. Failure events still reach the browser if saving the failure state fails. |
| Sample asset provenance | [scene notes](../samples/README.md), [provenance JSON](../samples/clip.provenance.json), [renderer](../scripts/create_demo_media.py) | Original 60-second illustrated scene, synthesized phone/door effects and 13 Google Cloud Text-to-Speech tracks. Sample fixtures are authored examples, not an accuracy benchmark. |
| Public source and license | [GitHub repository](https://github.com/Abhinav0905/Google_All_Agentic_Cinema), [Apache-2.0 license](../LICENSE), [setup](../README.md) | Published revision `c0fc1f3` includes the Postgres connection-health fix, locked build and explicit project virtual environment. The existing license is Apache-2.0. |
| Replit development and hosting | [Public app](https://google-all-agentic-cinema--abhinav0905.replit.app), [Agent work record](REPLIT_VERIFICATION.md), [.replit](../.replit), [build script](../scripts/replit_build.sh) | Agent checked runtime tools and Postgres, added `postgresql-16` and invoked the build before its quota stopped the task. Later manual work fixed installation and idle connections; revision `c0fc1f3` is published. Hosted live analysis, exports and the fresh browser live and idle checks passed. The [Replit track requirements](https://agentic-cinema.devpost.com/details/replit-resources) require both Agent use and Replit hosting. |

## Verification record

- Full local suite: **109 passed**, including the closed-connection regression.
- The exact Replit build script passed after the installer was directed to `.venv`. This was a manual check after the Agent quota stop; no complete Replit Agent test run is claimed.
- Public `/api/health`: HTTP 200, `ok=true`, Vertex configured in ADC mode, Postgres selected, bundled clip present and history persistence enabled. The response does not establish persistence after restart.
- Ruff checks passed for `engine`, `agents`, `api` and `tests`; `git diff --check` passed.
- Browser live review: all eight steps completed, 29 findings, phone-caption repair approved and SRT downloaded.
- Independent live API review: all eight steps completed in 51.16 seconds, 24 findings and 11 repair proposals. Repeated SRT exports matched, cross-session access was denied, and range playback worked.
- Hosted live review `60be0144`: all eight steps completed in 48.16 seconds, 36 findings and 23 proposals. One repair was approved, repeated exports matched, another session received 404 and a video range request received 206.
- Public browser sample `595edd8f`: 19 findings; approved phone caption confirmed in the downloaded 1,189-byte SRT. This is the authored sample, not live model evidence.
- After republishing `c0fc1f3`, that sample retained its findings and decision, loaded 60-second video metadata and exported the identical SRT.
- Fresh browser live run `df0c56c3` on `c0fc1f3`: all eight steps completed, 36 findings and 23 proposals. The downloaded JSON confirms completed status and live mode. The approved phone repair appears as `PHONE RINGS` in the actual 1,189-byte browser SRT download.
- Production idle check on `c0fc1f3`: HTTP 201 for review creation before and after 180.6 seconds of client idle time. This verifies the observed interval, not long-duration service reliability.
- The different finding counts are model variation, not a fixed expected score. These runs establish operation; they do not measure precision or recall.

The hosted Gemini Pro output incorrectly described a woman slapping a man; that event is absent from the original animation. FrameKind derived an audio-description finding from this false observation. This is a concrete model error, not a successful detection. Editors must inspect the source video before approving proposals. No automated accuracy or certification claim is supported by these runs.

The local verification workspace retains the live run and check summary. Do not publish session cookies, credentials or account screenshots as evidence. The remaining public proof is tracked in [submission readiness](SUBMISSION_READINESS.md).

## Submission assets

The [cover](screenshots/framekind-cover.png), [recording script](DEMO_SCRIPT.md), sample media and setup instructions exist. Devpost has the FrameKind title, story, repository, cover, public app link and additional information saved. The draft is at finalization, 3/5. A public video URL and final terms/action remain; the entry has not been formally submitted.

The [official rules](https://agentic-cinema.devpost.com/rules) require public source, a working project demonstration and a publicly visible YouTube or Vimeo video. Keep the video within three minutes and provide English narration or subtitles. The published deadline is September 9, 2026 at 2:00 p.m. PDT. Recheck the live form before the final submission.
