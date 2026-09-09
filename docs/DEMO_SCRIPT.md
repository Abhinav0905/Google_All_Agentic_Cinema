# FrameKind recording script

Updated September 9, 2026. Target: **2 minutes 45 seconds**, including the end card. Record at a readable browser size and add accurate English captions. Keep account pages, credentials and private session details out of the recording.

The idle-connection fix is published in `c0fc1f3`. The browser sample's findings, approved edit and identical SRT survived republishing. Fresh browser live run `df0c56c3` completed all eight steps with 36 findings and 23 proposals. Review creation returned HTTP 201 before and after 180.6 seconds of client idle time. The app is ready for this recording workflow.

Record the [public FrameKind app](https://google-all-agentic-cinema--abhinav0905.replit.app). Earlier hosted live run `60be0144` completed all eight steps in 48.16 seconds; repair export, session isolation and range playback passed. Public browser sample `595edd8f` exported its approved phone caption both before and after republishing. Start with the authored sample, then explicitly switch to the real uploaded-video result in the browser session that owns it.

| Time | Screen and action | Narration |
|---|---|---|
| 0:00–0:20 | Click **Step into a sample review**. Keep **Sample review** visible, turn original captions on with **CC** and seek to about 00:18.5. | "The phone on this desk rings, but there is no sound caption. A viewer watching without audio can miss it. This is our authored sample, which makes the review workflow repeatable. FrameKind helps editors catch these gaps before delivery." |
| 0:20–0:45 | Open the phone finding, seek and listen. Inspect the suggested caption, click **Approve edit**, then point to **Keep original** on another proposal. | "Each finding puts the timecode, evidence and proposed change beside the picture. I check what happened before accepting the edit. The editor keeps the final decision, and the original captions stay intact." |
| 0:45–1:05 | Click **SRT** and open the downloaded file at the inserted cue. Show the scorecard after the approved edit. | "Here is the exported cue. This is a caption file I can take back to an editing workflow. The review updates after approved changes, so I can see what remains. It checks our project thresholds; it does not certify accessibility." |
| 1:05–1:35 | Choose **New review**. Upload MP4 and SRT, click **Start review**, then expand **Behind the review**. | "Now I'll switch to a real uploaded-video review. Gemini on Google Cloud transcribes dialogue, listens for sounds and examines visual context. An eight-step Google ADK workflow combines those observations with timed-text checks and proposes repairs." |
| 1:35–2:00 | Show actual progress, then the completed **Live review**. Label any cut that removes waiting. Compare a finding with the clip; keep the invented visual event unapproved. | "This live result comes from the uploaded clip. The trace records each step. In our test, the visual model invented an event that never happened. That's why every proposal needs editor review. Caption-only runs are labeled separately, with media checks left unassessed." |
| 2:00–2:20 | Show **Review library**, return to a completed review and open **Review report**. Show the public Replit URL. | "Reviews and decisions are saved for this browser session. I can reopen the findings or export a report with timestamps and evidence. The picture, the problem and the repair stay together." |
| 2:20–2:45 | Show public GitHub and the development record, then return to FrameKind. | "The app is hosted on Replit. Its runtime uses Google Gemini and ADK. Development included Google Antigravity and Codex. Replit Agent helped check the environment and setup before its quota stopped the task. FrameKind gives editors a practical final pass, so more of the story reaches every audience." |

## Final recording checks

- Fresh browser live analysis and the bounded idle-period creation check passed. Sample history, its decision and identical export survived republishing. These are the demonstrated checks, not a guarantee of model accuracy or long-term availability.
- The hosted visual model invented a woman slapping a man. Do not present that finding as accurate or approve its proposed description. Keep the short model-error explanation in the narration.
- Do not say Replit Agent completed the test suite or republish checks. The 109 passing tests were run locally; later Replit build troubleshooting was manual.
- Keep the **Sample review** and **Live review** labels visible at each transition. The sample uses authored reference annotations, not recorded Gemini output.
- Use the public `.replit.app` address for the hosted segment. If any earlier local footage is retained, label it as local.
- Show the exported cue. A download button alone does not demonstrate a repaired file.
- Make wait-time cuts clear. Use a completed result from the same real upload, not a fixture substituted for a live result.
- Publish the complete video visibly on YouTube or Vimeo with English narration or subtitles. Check its public URL while signed out, then add it to Devpost.
- Keep development-tool disclosure consistent with [TOOLING.md](TOOLING.md). Accurate attribution does not establish contest eligibility.
