# FrameKind Replit verification record

Updated September 9, 2026. [Public app](https://google-all-agentic-cinema--abhinav0905.replit.app) · [Replit workspace](https://replit.com/@abhinav0905/GoogleAllAgenticCinema) · [Public source](https://github.com/Abhinav0905/Google_All_Agentic_Cinema).

The app is published with runtime revision `c0fc1f3`. Production uses Postgres, Google Vertex ADC credentials, one Uvicorn process and one Autoscale instance (2 vCPU, 4 GiB). The free deployment expires October 8, 2026. Check availability through the end of judging that day; no paid plan was purchased.

## Observed Replit Agent work

The automatic **Set up imported project** task inspected the README and recorded three actions. A bounded verification request followed, with two further batches of seven actions visible in the Agent session.

The Agent checked Python 3.11, Node 20, FFmpeg and FFprobe availability, confirmed Postgres was reachable, added the `postgresql-16` module and ran `bash scripts/replit_build.sh`. Its free quota stopped the task after about one minute. The Agent did not complete the test suite or restart checks. Later fixes and verification below were completed manually with Codex assistance.

## Build and publishing repairs

The imported core was `5a5f9a0`. The following changes were pushed to GitHub and applied to Replit:

- Bounded Python support to 3.11 and 3.12, checked in `uv.lock` and removed the unused direct `google-cloud-aiplatform` dependency. Runtime Vertex requests use the Google Gen AI SDK through ADC.
- Fixed a managed installer failure in `0edcde0`. Replit set `UV_PROJECT_ENVIRONMENT` to `.pythonlibs`, a user-package prefix without `pyvenv.cfg`. The installer tried to write `propcache` under the read-only Nix Python directory and failed with `Permission denied (os error 13)`.
- Set `UV_PROJECT_ENVIRONMENT=.venv` in `.replit`. An actual Replit Shell run created that environment, installed 77 packages and imported `fastapi`, `sqlalchemy` and `google.adk` successfully. The exact build script then passed: 1,602 frontend modules, 185.54 kB JavaScript and 33.82 kB CSS. Startup uses the same interpreter and installs nothing.
- Fixed an idle Postgres failure in `c0fc1f3`. The production log recorded `POST /api/runs` returning 500 with `psycopg.errors.AdminShutdown: terminating connection due to administrator command`. The Postgres pool now checks a connection before reuse. A regression test closes an idle connection and verifies a replacement reads the committed data. The full local suite passed: **109 tests**, with 16 dependency deprecation warnings. This protects connection checkout; it does not retry an interrupted active transaction.

References: [uv environment paths](https://docs.astral.sh/uv/concepts/projects/config/#project-environment-path) and [SQLAlchemy connection checks](https://docs.sqlalchemy.org/en/20/core/pooling.html#disconnect-handling-pessimistic).

## Verified production behavior

- The public home page loads, and `/api/health` reports `ok: true`, `vertex: true`, `vertex_mode: adc`, `database: postgres` and an available bundled clip. Credential values were never committed.
- Hosted live run `60be0144-2d37-4ce8-9751-17da5973700e` completed all eight steps, including three Gemini calls, in 48.16 seconds. It produced 36 findings and 23 repair proposals. One repair was accepted; repeated SRT exports were identical. Another browser session received 404 for the private run. Video Range requests returned 206.
- Public browser sample `595edd8f-4195-4752-8c85-6ba5f439603e` completed with 19 findings. The phone-caption proposal was approved. The downloaded `framekind-595edd8f.srt` is 1,189 bytes and contains `[PHONE RINGS]`.
- After republishing `c0fc1f3`, that same browser reopened the saved sample, its approved decision and the 60-second video. A second SRT download was byte-for-byte identical to the download before republishing. This verifies the sample's saved record and decision across replacement of the serving process.
- Fresh browser upload `df0c56c3-4cde-49cf-8baa-6eb58fd9cba3` on `c0fc1f3` completed all eight steps with 36 findings and 23 proposals. The actual JSON report downloaded. A phone-caption repair was approved and its 1,189-byte SRT downloaded.
- A separate client created a review, waited 180.6 seconds and created another successfully. Both responses were HTTP 201 after the connection fix.

The earlier hosted model result invented a visual event, a woman slapping a man, that is absent from the authored animation. It is a model error. Proposed findings require human review; successful execution is not measured accuracy or accessibility certification.

The local workspace retains hosted JSON and export checks under ignored `work/verification/hosted/`. These are manual test results, not Replit Agent results. The development-tool eligibility conflict remains documented in [TOOLING.md](TOOLING.md). The demo video and formal Devpost submission are separate remaining steps.
