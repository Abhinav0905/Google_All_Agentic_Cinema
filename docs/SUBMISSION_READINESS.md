# FrameKind submission readiness

Status checked September 9, 2026: **[FrameKind revision `c0fc1f3` is publicly deployed on Replit](https://google-all-agentic-cinema--abhinav0905.replit.app), with the browser live and idle-period checks passed.** A sample retained its findings, approved decision and identical export after republishing. Devpost story, app link and additional information are saved; the draft is at finalization, 3/5. The remaining submission work is the public video and final entry action, including the entrant's terms review.

## What is ready

| Item | Current evidence |
|---|---|
| Local live workflow | Two uploaded-video runs completed all eight steps. One browser run had 29 findings; an independent API run had 24 findings and 11 proposals. |
| Public deployment | The public home page loads. `/api/health` returns HTTP 200 with `ok=true`, `vertex=true`, ADC mode, `database=postgres`, `sample_clip=true` and `history_persisted=true`. These are health/configuration checks, not a restart-persistence test. |
| Hosted live workflow | Run `60be0144` completed all eight steps, including three Gemini calls, in 48.16 seconds. It produced 36 findings and 23 repair proposals. This verifies operation, not the accuracy of every finding. |
| Fresh browser live workflow | Run `df0c56c3` on `c0fc1f3` completed all eight steps, with 36 findings and 23 proposals. The downloaded JSON confirms completed status and live mode. Its phone repair was approved in the browser and the actual 1,189-byte SRT contains `PHONE RINGS`. |
| Hosted review and delivery | One live repair was approved through the API; repeated SRT exports matched. A different session received 404, and video range playback returned 206. Public browser sample `595edd8f` completed with 19 findings; its approved phone repair appeared in the actual 1,189-byte SRT download. |
| Regression checks | 109 local tests passed, including the closed-connection regression. Ruff and diff whitespace checks passed. These are not Replit Agent test results. |
| Persistence after republishing | Both sample `595edd8f` and uploaded live review `df0c56c3` retained their findings, approved edits and identical 1,189-byte SRT exports after republishing. The uploaded 60-second video loaded from its hosted media route after a full page reload. |
| Production idle check | On `c0fc1f3`, review creation returned HTTP 201 before and after 180.6 seconds of client idle time. This is a bounded regression check, not a long-duration reliability benchmark. |
| Demo scene | Original illustrated MP4 with Google Cloud synthetic dialogue and authored sound effects; [provenance](../samples/README.md) is recorded. |
| Public source | Published revision `c0fc1f3` in the [GitHub repository](https://github.com/Abhinav0905/Google_All_Agentic_Cinema) adds Postgres connection health checks to the locked build and explicit project virtual environment. Apache-2.0 is retained. |
| Replit work | Agent checked runtime tools and Postgres, added `postgresql-16` and invoked the build before reaching its free quota. Later manual work fixed the installer target; the exact `bash scripts/replit_build.sh` now passes in Replit. Run preview displays FrameKind. The [Agent record](REPLIT_VERIFICATION.md) describes its partial task, not the later checks. |
| Submission materials | Cover, architecture, tooling record, [evidence map](JUDGE-EVIDENCE-MAP.md) and [demo script](DEMO_SCRIPT.md) exist. Devpost title, story, GitHub, cover, public app link and additional information are saved. Finalization shows draft 3/5; video and final terms/action remain. |

The first real media run failed while persisting duplicate finding IDs. That defect was fixed and covered by regression tests; later local and hosted runs completed. Model output still needs review. In the hosted run, Gemini Pro invented a woman slapping a man, which does not occur in the original animation; FrameKind then proposed an audio-description finding based on it. Sound labels also varied across runs. Do not approve such findings without checking the clip, claim a measured accuracy rate or describe the app as a certified assessment.

## Remaining work, in order

| Step | Action and completion evidence | Planning allowance |
|---|---|---|
| 1 | Record the working app using the demo script. Check each demonstrated finding against the clip and leave the invented visual event unapproved. Show a real approval and exported cue. Keep the full video under three minutes, add accurate English captions and publish it visibly on YouTube or Vimeo. Open the public URL while signed out. | 30–45 minutes |
| 2 | Add the public video URL to Devpost and check playback. The app link, story and additional information are already saved. | 5 minutes |
| 3 | Have the entrant review the final terms, complete the final Devpost action and verify the resulting confirmation and project status. A draft at finalization does not prove entry into the contest. | 5–10 minutes |

These are planning allowances, not a guarantee that account setup or deployment will finish within them. The [official deadline](https://agentic-cinema.devpost.com/rules) is September 9, 2026 at 2:00 p.m. PDT.

## Safe deployment configuration

- Use `bash scripts/replit_build.sh` for installation and build, then `bash scripts/replit_start.sh` to serve the app. The build requires `uv` and runs `UV_PROJECT_ENVIRONMENT=.venv uv sync --frozen --no-dev`. Explicit `.venv` targeting fixes Replit's read-only Nix/user-package-prefix install failure. Boot uses the project environment and does not reinstall dependencies.
- Keep one serving process and one instance. The `.replit` Autoscale target is `cloudrun`; set Publishing > Adjust settings > Machine configuration > Max machines to **1**. Jobs, event streams and request limits are process-local.
- Attach Postgres through `DATABASE_URL`. Local SQLite passed the current checks, but an ephemeral deployment filesystem does not provide durable hosted history. Both run records and uploaded assets are stored in the database.
- Configure Google credentials in Replit Secrets, never in source or Agent chat. The locally verified path uses ADC/service-account JSON with `GOOGLE_CLOUD_PROJECT` and `GOOGLE_CLOUD_LOCATION=global`. Inline clips are capped at 14 MiB and do not need a GCS bucket.
- A green configuration badge only confirms settings are present. Verify an actual hosted model call before calling deployment complete.
- Keep the browser open during a live review. There is no durable job queue or multi-instance coordination. Anonymous browser cookies identify review ownership; this is not a cross-device account system.
- Replit currently lists October 8, 2026 as deployment expiry. Maintain the app through the full judging window; verify the exact expiry time and extend availability if needed.

Deployment commands and the Agent verification prompt are in [TOOLING.md](TOOLING.md). Replit logs identified a terminated Postgres connection behind an idle-time `POST /api/runs` failure. Revision `c0fc1f3` enables `pool_pre_ping` and is published; 109 local tests pass. Sample history, its approved decision and identical export survived republishing. A fresh browser live run completed on the new revision. The production idle check then returned HTTP 201 both before and after 180.6 seconds of client idle time.

## Claims that must stay accurate

The sample button uses authored annotations and is labeled **Sample review**. Show a completed **Live review** when explaining Gemini analysis. The scorecard checks project thresholds; it does not certify broadcaster compliance. Every model-generated sound label or repair remains a proposal.

The development record includes Google Antigravity, Codex and the documented Replit Agent setup work. The organizer's [AI-tool clarification](https://agentic-cinema.devpost.com/forum_topics/44644-question-about-the-ai-usage-limitation-grafana-track) restricts assistance across the development process. That conflicts with the recorded Codex work; neither testing nor the later Replit session establishes eligibility. Do not claim exclusive Google-tool development or guaranteed contest acceptance.
