# FrameKind final recording script

Revised September 9, 2026. Record each numbered part separately, then join them. Read only the quoted narration. Target **2:45-2:50**, including short pauses and the end card; keep the finished video under three minutes. The time ranges below are editing targets, not measured speaking times.

## Before recording

- Open [FrameKind](https://google-all-agentic-cinema--abhinav0905.replit.app) and the [public repository](https://github.com/Abhinav0905/Google_All_Agentic_Cinema).
- Have these existing files ready: [clip.mp4](../samples/clip.mp4), [captions_bad.srt](../samples/captions_bad.srt) and, optionally, [ad_script.srt](../samples/ad_script.srt). On this Mac they are in `/Users/mac001/Desktop/Google_All_Agentic/samples/`. In a file picker, press Command+Shift+G and paste that folder path.
- Use the same browser session for a live upload and its completed result. Incognito is fine while that session stays open; closing all incognito windows loses its anonymous review access.
- The sample is authored test material with deliberately incomplete captions. Keep **Sample review** visible in parts 2-4. Part 5 uploads the clip for fresh Gemini analysis; show **Live media analysis** when it completes.
- Leave a second of silence at each end of a take. Cut upload and analysis waiting time, with an on-screen label such as `Analysis wait shortened`.

## 1. The problem and the audience | 0:00-0:25

**Show:** FrameKind homepage. Keep the app name and main action visible.

> For deaf and hard-of-hearing viewers, captions carry part of the story. Missing sounds or text that disappears too quickly can leave gaps. I'm Abhinav, and I built FrameKind to give film editors a second pass over their existing captions before delivery.

## 2. Inspect and approve a possible gap | 0:25-0:50

**Show:** Click **Step into a sample review**. Select **All** in the findings panel, then scroll inside that panel to **A sound is missing** near **00:18**. Select the phone finding. Click **Play film** to hear it, inspect the proposal and click **Approve edit**. Show **Approved for export**.

> This is our authored sample. The phone rings, but the supplied captions don't mention it. I open the finding, play the scene and inspect the suggested cue. After checking the evidence, I approve the edit. The original captions stay intact.

## 3. Show another kind of issue | 0:50-1:10

**Show:** Select **Too much to read** near **00:06**. Point to its reading-speed evidence. If time permits, briefly open **Description overlaps dialogue** near **00:05**. Do not approve the reading-speed proposal: its current suggestion requires manual work and does not change the text or timing.

> Here, the caption contains too much text for the time available. FrameKind flags its reading speed for review. When an audio-description script is supplied, it can also flag narration that overlaps dialogue.

## 4. Prove the repair reaches a usable file | 1:10-1:30

**Show:** Click **SRT** below the player. Open the downloaded file and find `PHONE RINGS`. Show the cue and its timestamp. The player continues displaying the original captions, so demonstrate the repair in the exported file.

> Now I export the caption file. Here is the phone cue I approved, with its timestamp. Only approved changes enter this export. The editor can take the file back into their editing workflow.

## 5. Run fresh media analysis | 1:30-1:55

**Show:** Choose **New review**. Under **Your film**, select `clip.mp4`; under **Captions**, select `captions_bad.srt`. Keep **Sound & speaker checks** enabled. The audio-description file is optional. Click **Start review**, expand **Behind the review** and capture the real processing steps. Label any cut that removes waiting.

> Now I'm uploading a video and its existing captions for fresh analysis. Gemini on Google Cloud transcribes dialogue, listens for sound events and examines visual context. A Google ADK workflow combines those observations with caption checks. Behind the review shows each processing step.

## 6. Show the completed result and editor judgment | 1:55-2:20

**Show:** The completed **Live media analysis** from that upload. Open a finding and compare it with the clip. Keep unsupported findings unapproved, or click **Keep original** on an unsupported proposal. Do not substitute the authored sample for the live result.

> This result comes from the uploaded video. I can jump from a finding back to the scene. AI can make mistakes: in testing, the visual model described an event that wasn't there. That's why the editor reviews every proposed change.

## 7. Saved work, development and closing | 2:20-2:50

**Show:** **Review library**, reopen the completed **Media review** and briefly show **Review report**. Show the Replit address and public GitHub repository, then return to FrameKind for the last sentence.

> FrameKind runs on Replit, with saved reviews and downloadable reports. Development used Antigravity, Cursor, Codex and Replit Agent; the runtime AI uses Google Gemini. The source is public on GitHub. FrameKind brings the scene, the suspected problem and the approved repair together, so editors can make informed decisions before delivery.

## Recording checks, not narration

- Position this as a second review of existing captions. Sound captioning and caption quality checks already exist; no first-of-its-kind claim is supported.
- The phone example demonstrates an approved insertion. The reading-speed example demonstrates detection; do not present its unchanged manual proposal as a completed repair.
- Missing-sound detection currently checks for a nearby sound tag. It does not verify that the tag names the correct sound. Do not claim exhaustive sound coverage or semantic correctness.
- Prior hosted Gemini output invented a visual event absent from the clip. Findings remain proposals; no measured accuracy, certified accessibility or customer time saving has been established.
- Replit Agent inspected the environment and performed setup/build work before reaching its quota. Do not credit it with completing the test suite or all deployment checks. Development attribution remains in the repository and submission materials.
- Historical verification includes 109 passing local tests, completed hosted media reviews and approved exports that survived redeployment. These are bounded checks, not a new verification run performed for this script revision. See [readiness](SUBMISSION_READINESS.md).
- Keep private account pages and credentials out of the recording. Add accurate English captions to the finished video, including relevant sound cues. Check that the public video plays while signed out before placing its URL in Devpost.
- The organizer's [AI-tool clarification](https://agentic-cinema.devpost.com/forum_topics/44644-question-about-the-ai-usage-limitation-grafana-track) conflicts with the recorded third-party development assistance. This script does not establish contest eligibility.
