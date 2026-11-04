# The Briefing: an authored FrameKind test scene

`clip.mp4` is an original 60-second illustrated conference-room scene. The artwork is drawn by `scripts/create_demo_media.py` with Pillow. Phone ringing and a closing-door sound are synthesized from mathematical waveforms with a fixed noise seed. No film footage, stock artwork, music or downloaded sound effects are used.

The current rendered clip includes thirteen Google Cloud Text-to-Speech tracks: `en-US-Neural2-D` for Alex and `en-US-Neural2-F` for Sarah. The synthesis used 776 characters of authored dialogue. Voice IDs, source filenames and tempo adjustments are recorded in `clip.provenance.json`.

The current voice-track state is recorded in `clip.provenance.json` and visibly labeled in the video. A clip marked "speech track pending" contains the phone and door effects but no spoken dialogue. Do not describe that version as a transcription demonstration. When all thirteen voice files are supplied, the renderer fits them to the authored intervals and changes the label to "Synthetic voices + authored sound effects".

The scene follows the existing authored fixture timeline:

| Time | Authored event |
|---|---|
| 00:09 | Q3 financial report and confidential label appear on the screen |
| 00:18.500 | A phone rings on the table |
| 00:27.500 | Sarah's optional voice speaks off screen |
| 00:50 | Sarah enters with a folder |
| 00:56 | The door closes with a slam |

The JSON files under `tests/fixtures/` are an authored review scenario. They are **not a measured accuracy benchmark or evidence that Gemini analyzed this video**. The historical `source` values inside those fixture files do not change their status as fixture data. The app's Sample mode replays these records. Only a separately executed Live run can demonstrate model analysis of the actual media.

`captions_bad.srt` intentionally contains missing cues, formatting defects and timing errors. This is useful for checking whether accepted changes survive export, including after a page reload. The fixture dialogue has some unusually tight intervals; synthetic voice files may be accelerated to fit those intervals. The resulting tempo factors are recorded in the provenance JSON.

## Render or add speech

Requirements: Python with Pillow, plus `ffmpeg` and `ffprobe` on PATH.

```sh
python3 scripts/create_demo_media.py
```

To include separately generated voice clips, place WAV files named `segment_00.wav` through `segment_12.wav` in `work/demo_voice/`, following the order in `tests/fixtures/transcribe_fixture.json`, then run:

```sh
python3 scripts/create_demo_media.py --voice-dir work/demo_voice
```

The renderer requires all thirteen files when `--voice-dir` is supplied. It preserves the fixture start/end windows, writes an H.264/AAC MP4 with fast-start metadata and records the voice source filenames and time adjustments. Temporary visuals and sound-effect WAVs go under `work/demo_media/`.

The original illustration, sound-effect synthesis and rendering source are included under this repository's Apache-2.0 license. The current speech was generated with the official Google Cloud Text-to-Speech `text:synthesize` endpoint and the Neural2 voice IDs listed above. Replacements should preserve their own provider and voice provenance.
