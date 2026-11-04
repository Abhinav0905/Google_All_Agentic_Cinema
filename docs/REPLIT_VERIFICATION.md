# FrameKind Replit verification record

Recorded September 8, 2026. [Replit workspace](https://replit.com/@abhinav0905/GoogleAllAgenticCinema): imported core revision `5a5f9a0`. Public GitHub head `7184eff` contains the initial evidence documents. This record separates observed Agent actions from checks completed manually and checks still pending.

## Observed Replit Agent work

The automatic **Set up imported project** task inspected the README and recorded three actions. A bounded verification request followed, with two further batches of seven actions visible in the Agent session.

The Agent checked Python 3.11, Node 20, FFmpeg and FFprobe availability, and confirmed Postgres was reachable. It added the `postgresql-16` module to `.replit` in the Replit workspace and ran `bash scripts/replit_build.sh`.

The free Agent quota was exhausted after about one minute of the bounded task. The full verification request did not finish. There is no completed Agent test-suite, sample-repair or process-restart result to report. The module edit above is a Replit workspace change; confirm it is included in public source before claiming the repository exactly matches that workspace.

## Manual checks after the quota stop

- Replit Shell confirmed that `web/dist/index.html` exists and Python can import `fastapi` and `sqlalchemy`. The check printed `build dependencies ready`.
- The user entered the service-account JSON in Replit Secrets. `GOOGLE_CLOUD_PROJECT` and `GOOGLE_CLOUD_LOCATION=global` were configured. No credential contents are recorded here.
- Replit **Run** opened the FrameKind home screen in its development preview. The interface displayed **Multimodal configured**. That badge confirms configuration is present; it does not prove a hosted Gemini call succeeded.
- Publishing is in progress. A public app URL has not yet been verified.

The two successful live Vertex reviews and 108 passing tests described in [submission readiness](SUBMISSION_READINESS.md) were local checks. They are not Replit Agent test results.

## Checks still required

- Open the finished public app URL in a fresh browser and confirm the app and bundled video load.
- Complete a sample review, approve one repair and inspect the exported SRT. Repeat the export and compare it.
- Run an actual uploaded-video review in the published environment and confirm all three Gemini steps complete.
- Confirm run history, accepted decisions and uploaded media survive a process restart with the same browser cookie and the production database.
- Confirm a different browser session cannot access that run, its events, media or exports.
- Verify deployment uses one serving process and one instance, and record the final deployed revision and public URL.

Replit Agent contributed the setup work above. Public hosting remains a separate pending check. This record does not resolve the development-tool eligibility issue documented in [TOOLING.md](TOOLING.md).
