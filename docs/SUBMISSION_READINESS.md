# FrameKind submission readiness

Status checked September 8, 2026: **the app works locally; publishing and the final entry are unfinished.** Two real Google Vertex media reviews completed. The Devpost project is a saved draft, not a formally submitted entry.

## What is ready

| Item | Current evidence |
|---|---|
| Local live workflow | Two uploaded-video runs completed all eight steps. One browser run had 29 findings; an independent API run had 24 findings and 11 proposals. |
| Review and delivery | A phone-caption repair was approved in the browser and SRT downloaded. The API check confirmed identical repeated exports, private run access and HTTP 206 media playback. |
| Regression checks | 108 tests passed, with 16 dependency deprecation warnings. Ruff and diff whitespace checks passed. |
| Demo scene | Original illustrated MP4 with Google Cloud synthetic dialogue and authored sound effects; [provenance](../samples/README.md) is recorded. |
| Public source | FrameKind core revision `5a5f9a0` is pushed to the [GitHub repository](https://github.com/Abhinav0905/Google_All_Agentic_Cinema); the remote revision was verified. Apache-2.0 is retained. Final evidence documents need a follow-up push. |
| Submission materials | Cover, architecture, tooling record, [evidence map](JUDGE-EVIDENCE-MAP.md) and [demo script](DEMO_SCRIPT.md) exist. Title, story, GitHub link and cover are saved in the Devpost draft. |

The first real media run failed while persisting duplicate finding IDs. That defect was fixed and covered by regression tests; the two later runs completed. Gemini assigned different labels to some sounds across runs. Keep human review central in the demo and write-up. Do not describe FrameKind as a certified accessibility assessment or claim a measured accuracy rate.

## Remaining work, in order

| Step | Action and completion evidence | Planning allowance |
|---|---|---|
| 1 | Push these final evidence documents as a follow-up to core revision `5a5f9a0`. Open GitHub and verify the current source, license, sample MP4 and setup instructions. Keep credentials and local verification cookies out of the commit. | 5–10 minutes |
| 2 | Complete Replit setup. Phone verification and repository import are complete; Starter is selected and the automatic Agent setup task is running. Run the bounded verification task in [TOOLING.md](TOOLING.md), then save actual checks and changes in `docs/REPLIT_VERIFICATION.md`. An import alone is not evidence of completed Agent work. | 20–40 minutes, build dependent |
| 3 | Configure server secrets and durable Postgres, build, publish and open the public URL in a fresh browser. Confirm sample review, one approved export, one live upload and same-session history after restart. Check another session cannot access the run. | 20–40 minutes, deployment dependent |
| 4 | Record the working app using the demo script. Show an actual finding, approval and exported cue. Keep the complete video under three minutes, add accurate English captions and publish it visibly on YouTube or Vimeo. Open its public URL while signed out. | 30–45 minutes |
| 5 | Add the verified app and video URLs to Devpost. Finish and save additional-information fields using the entrant's own answers. Recheck the story against the final deployed behavior and disclose Google Antigravity and Codex development assistance accurately. | 10–15 minutes |
| 6 | Complete the final Devpost action and verify the resulting confirmation and project status. A saved draft, uploaded cover or public repository does not prove entry into the contest. | 5–10 minutes |

These are planning allowances, not a guarantee that account setup or deployment will finish within them. The [official deadline](https://agentic-cinema.devpost.com/rules) is September 9, 2026 at 2:00 p.m. PDT.

## Safe deployment configuration

- Use `bash scripts/replit_build.sh` for installation and build, then `bash scripts/replit_start.sh` to serve the app. Boot does not reinstall dependencies.
- Keep one serving process and one instance. The `.replit` Autoscale target is `cloudrun`; set Publishing > Adjust settings > Machine configuration > Max machines to **1**. Jobs, event streams and request limits are process-local.
- Attach Postgres through `DATABASE_URL`. Local SQLite passed the current checks, but an ephemeral deployment filesystem does not provide durable hosted history. Both run records and uploaded assets are stored in the database.
- Configure Google credentials in Replit Secrets, never in source or Agent chat. The locally verified path uses ADC/service-account JSON with `GOOGLE_CLOUD_PROJECT` and `GOOGLE_CLOUD_LOCATION=global`. Inline clips are capped at 14 MiB and do not need a GCS bucket.
- A green configuration badge only confirms settings are present. Verify an actual hosted model call before calling deployment complete.
- Keep the browser open during a live review. There is no durable job queue or multi-instance coordination. Anonymous browser cookies identify review ownership; this is not a cross-device account system.

Deployment commands and the Agent verification prompt are in [TOOLING.md](TOOLING.md). The current local success does not verify Replit Postgres, deployed secrets, public video playback or hosted model access.

## Claims that must stay accurate

The sample button uses authored annotations and is labeled **Sample review**. Show a completed **Live review** when explaining Gemini analysis. The scorecard checks project thresholds; it does not certify broadcaster compliance. Every model-generated sound label or repair remains a proposal.

The development record includes Google Antigravity and Codex. Replit Agent setup has started, but completed work has not yet been verified. The organizer's [AI-tool clarification](https://agentic-cinema.devpost.com/forum_topics/44644-question-about-the-ai-usage-limitation-grafana-track) restricts assistance across the development process. That conflicts with the recorded Codex work; neither testing nor a later Replit session establishes eligibility. Do not claim exclusive Google-tool development or guaranteed contest acceptance.
