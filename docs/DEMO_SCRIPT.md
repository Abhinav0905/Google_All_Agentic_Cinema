# FrameKind recording script

Target: 2 minutes 45 seconds. Record the working app at a readable browser size. Keep account pages and secrets out of the recording. Add accurate English captions to the final video. Publish it on YouTube or Vimeo and use the public URL in Devpost.

Before the final recording, complete one real uploaded-video run successfully on the hosted app. Keep that result ready in **Review library**. Local live runs have passed, but hosted verification is still pending. The built-in **Step into a sample review** button is useful for repeatable repair clicks; describe it as an authored sample. Do not call it a live model result.

| Time | Screen and action | Say this |
|---|---|---|
| 0:00–0:20 | Open the demo clip with original captions enabled using **CC**. Seek to the phone at about 00:18.5. | "The phone on this desk rings, but there is no sound caption. A viewer watching without audio can miss that event. FrameKind helps editors catch gaps like this before they deliver a cut." |
| 0:20–0:45 | Choose **New review**, upload a short MP4 and its SRT, then click **Start review**. | "I upload the picture and the existing captions. FrameKind runs an eight-step workflow with Google ADK. Gemini on Google Cloud transcribes speech, listens for sounds and checks the visual context. Then timed-text rules turn that evidence into specific findings." |
| 0:45–1:05 | Expand **Behind the review**. Show actual progress and the completed live run. Label any cut that removes waiting. | "The progress trace tells me what ran and where the evidence came from. If a model call fails, the review reports the failure. A caption-only review is labeled separately, with media checks left unassessed." |
| 1:05–1:40 | Open the phone finding, seek, listen and inspect its proposal. Click **Approve edit**. Point out **Keep original**. Introduce any switch to the authored sample. | "Here is the missing-sound finding. I can jump to the moment, check the evidence and review the proposed caption. Model labels can be wrong, so the editor decides what belongs in the film. I'll approve this repair. The original caption file stays intact." |
| 1:40–2:05 | Click **SRT**, open the downloaded file and point to the inserted cue. Show the result after approved changes. | "This produces a real caption file for the editing workflow. The accepted repair is in the export. FrameKind recalculates the review after approved changes, so I can see what remains. These are review checks, not an accessibility certification." |
| 2:05–2:25 | Show **Review library**, open **Review report**, then show the verified public app URL. | "The review and decisions are saved for this browser session. I can return to the findings and export a report with timestamps and evidence. The interface keeps the picture, the problem and the proposed repair together." |
| 2:25–2:45 | Show public GitHub and the truthful development record. If Replit Agent work and public deployment are complete, show that evidence too. | "The runtime uses Google Gemini and ADK. Development included Google Antigravity and Codex. The repository includes the code, sample assets, tests and setup instructions. FrameKind gives editors a practical final pass, so more of the story reaches every audience." |

## Recording checks

- Once verified, add: "We used Replit Agent to check the deployment, and the app is hosted on Replit." Do not record that claim before the Agent session and public URL exist.
- If preparing footage locally, label it as local. Replace the hosted-app segment after publication; a local address does not establish Replit deployment.
- Show an actual exported cue, not just the download button.
- Keep any wait-time edits obvious. Do not turn a fixture run into a fake live run.
- Keep the full video under 3 minutes, including intro and end card.
- Development-tool disclosure must match `docs/TOOLING.md`; do not say the app was built only with Google tools.
- Copy the final public video URL into the Devpost draft. A local recording is not a submitted entry.
